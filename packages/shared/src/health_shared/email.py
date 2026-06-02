"""Email sending behind a small interface.

M0/M1 decision: Resend is the provider. The interface keeps the provider swappable and
lets dev/test run without sending anything. The api (magic links) and, later, the worker
(briefings) both depend on this.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("health_shared.email")


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str | None = None


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Dev/test sender: logs the email and prints the body instead of delivering it.

    Printing the body is what makes magic-link login usable locally without a provider.
    """

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "email sent (console)",
            extra={"to": message.to, "subject": message.subject},
        )
        body = message.text or message.html
        print(f"\n--- EMAIL to {message.to} ---\n{message.subject}\n\n{body}\n--- end email ---\n")


class ResendEmailSender:
    """Sends via the Resend HTTP API (POST /emails, Bearer auth).

    Request shape verified against Resend's send-email API; covered by test_email.py.
    """

    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, message: EmailMessage) -> None:
        import httpx

        payload: dict[str, object] = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
        }
        if message.text:
            payload["text"] = message.text
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
            timeout=15,
        )
        if resp.is_error:
            # Surface Resend's reason (e.g. "domain not verified") instead of a bare status.
            logger.error(
                "resend send failed",
                extra={"status": resp.status_code, "body": resp.text[:1000], "to": message.to},
            )
            resp.raise_for_status()
        logger.info("email sent (resend)", extra={"to": message.to, "subject": message.subject})


def get_email_sender() -> EmailSender:
    """Pick the sender from the environment: Resend when configured, else console."""
    api_key = os.environ.get("RESEND_API_KEY")
    # resend.dev is Resend's shared test sender; replace with a verified domain in prod.
    sender = os.environ.get("EMAIL_FROM", "Health Agent <onboarding@resend.dev>")
    if api_key:
        return ResendEmailSender(api_key=api_key, sender=sender)
    return ConsoleEmailSender()
