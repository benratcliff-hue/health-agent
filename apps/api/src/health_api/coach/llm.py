"""LLM access for the coach, behind an interface.

A real Anthropic-backed coach (streaming for chat, complete for briefings) and a
deterministic stub used when no API key is configured, so the app and its tests run
without network or credentials. Model defaults to Haiku 4.5 (PRD 9.2).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Protocol

from health_api.config import Settings

logger = logging.getLogger("health_api.coach")

# A chat turn: {"role": "user" | "assistant", "content": str}
ChatMessage = dict[str, str]


class Coach(Protocol):
    def stream(self, system: str, messages: list[ChatMessage], usage_out: dict) -> Iterator[str]:
        """Yield reply text chunks; populate usage_out (tokens) once the stream ends."""

    def complete(self, system: str, messages: list[ChatMessage]) -> tuple[str, dict]:
        """Return (full reply text, usage) without streaming. Used for briefings."""


class StubCoach:
    """Deterministic, no-network coach for dev and tests."""

    def __init__(self, model: str) -> None:
        self._model = model

    def _reply(self, messages: list[ChatMessage]) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"[stub coach] You said: {last!r}. Set ANTHROPIC_API_KEY for real coaching."

    def stream(self, system: str, messages: list[ChatMessage], usage_out: dict) -> Iterator[str]:
        for word in self._reply(messages).split(" "):
            yield word + " "
        usage_out.update({"input_tokens": 0, "output_tokens": 0, "model": self._model})

    def complete(self, system: str, messages: list[ChatMessage]) -> tuple[str, dict]:
        return self._reply(messages), {"input_tokens": 0, "output_tokens": 0, "model": self._model}


class AnthropicCoach:
    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def _system_blocks(self, system: str) -> list[dict]:
        # cache_control on the stable system context; Haiku caches prefixes >= ~4096
        # tokens, so short contexts simply won't cache (no error, just no savings).
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _usage(self, usage) -> dict:
        return {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
            "model": self._model,
        }

    def stream(self, system: str, messages: list[ChatMessage], usage_out: dict) -> Iterator[str]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self._system_blocks(system),
            messages=messages,
        ) as stream:
            yield from stream.text_stream
            usage_out.update(self._usage(stream.get_final_message().usage))

    def complete(self, system: str, messages: list[ChatMessage]) -> tuple[str, dict]:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self._system_blocks(system),
            messages=messages,
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return text, self._usage(msg.usage)


def get_coach(settings: Settings) -> Coach:
    if settings.anthropic_api_key:
        return AnthropicCoach(
            api_key=settings.anthropic_api_key,
            model=settings.coach_model,
            max_tokens=settings.coach_max_tokens,
        )
    logger.info("no ANTHROPIC_API_KEY set; using stub coach")
    return StubCoach(model=settings.coach_model)
