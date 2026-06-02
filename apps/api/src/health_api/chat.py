"""Chat coach endpoint: POST /v1/chat, streamed over SSE.

The request persists the user turn, builds context, then streams the assistant reply.
The final assistant turn and its token usage are persisted from a fresh DB session inside
the streaming generator (the request-scoped session is gone by the time the body streams).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from health_api.auth import get_current_user
from health_api.config import get_settings
from health_api.db import get_db
from health_db import get_sessionmaker
from health_db.models import Conversation, Message, User
from health_shared.coach import get_coach
from health_shared.coach.context import build_system_prompt, load_history

logger = logging.getLogger("health_api.chat")

router = APIRouter(prefix="/v1")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat")
def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    # Resolve or create the conversation, then persist the user's turn (committed by get_db).
    conversation = None
    if body.conversation_id:
        conversation = db.get(Conversation, body.conversation_id)
        if conversation is not None and conversation.user_id != user.id:
            conversation = None
    if conversation is None:
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.flush()

    db.add(Message(conversation_id=conversation.id, role="user", content=body.message))
    conversation.last_message_at = datetime.now(UTC)

    # Flush so the just-added user turn is visible to load_history's query.
    db.flush()
    system = build_system_prompt(db, user)
    history = load_history(db, conversation)

    conversation_id = str(conversation.id)
    settings = get_settings()
    # Commit now (not at request teardown) so the conversation + user turn exist in the DB
    # before the streaming generator's separate session writes the assistant turn against
    # them; otherwise the assistant insert hits a foreign-key violation.
    db.commit()

    def generate() -> Iterator[str]:
        yield _sse({"conversation_id": conversation_id})
        coach = get_coach(
            settings.anthropic_api_key, settings.coach_model, settings.coach_max_tokens
        )
        usage: dict = {}
        chunks: list[str] = []
        try:
            for chunk in coach.stream(system, history, usage):
                chunks.append(chunk)
                yield _sse({"text": chunk})
        except Exception:
            logger.exception("coach stream failed")
            yield _sse({"error": "coach unavailable"})
            return

        reply = "".join(chunks)
        # Persist the assistant turn from a fresh session — the request session is closed.
        sessionmaker = get_sessionmaker(settings.database_url)
        with sessionmaker() as wdb:
            wdb.add(
                Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=reply,
                    tokens_in=usage.get("input_tokens"),
                    tokens_out=usage.get("output_tokens"),
                    model=usage.get("model"),
                )
            )
            conv = wdb.get(Conversation, conversation_id)
            if conv is not None:
                conv.last_message_at = datetime.now(UTC)
            wdb.commit()
        logger.info("chat reply", extra={"user_id": str(user.id), **usage})
        yield _sse({"done": True})

    return StreamingResponse(generate(), media_type="text/event-stream")
