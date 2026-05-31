"""Shared infrastructure and types across services.

Holds cross-service concerns (e.g. email sending) and, later, shared types and the coach
prompt templates from PRD Appendix A.
"""

from health_shared.email import (
    ConsoleEmailSender,
    EmailMessage,
    EmailSender,
    ResendEmailSender,
    get_email_sender,
)

__all__ = [
    "EmailMessage",
    "EmailSender",
    "ConsoleEmailSender",
    "ResendEmailSender",
    "get_email_sender",
]
