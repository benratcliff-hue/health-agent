"""Shared coach: context building + LLM access, used by the api (chat) and worker (briefings)."""

from health_shared.coach.llm import ChatMessage, Coach, get_coach

__all__ = ["Coach", "ChatMessage", "get_coach"]
