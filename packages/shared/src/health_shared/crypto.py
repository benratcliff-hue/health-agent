"""Symmetric encryption for secrets at rest (e.g. OAuth tokens), PRD 11.2.

Fernet (AES-128-CBC + HMAC) with a key from configuration. JSON in, opaque string out,
suitable for storing in a JSONB/text column.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet


def encrypt_json(key: str, data: dict[str, Any]) -> str:
    return Fernet(key.encode()).encrypt(json.dumps(data).encode()).decode()


def decrypt_json(key: str, token: str) -> dict[str, Any]:
    return json.loads(Fernet(key.encode()).decrypt(token.encode()).decode())
