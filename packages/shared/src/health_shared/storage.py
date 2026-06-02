"""Object storage behind a small interface (meal photos now; PDF labs later).

Decision (PRD 13): Cloudflare R2, accessed via its S3-compatible API with boto3. R2 has no
egress fees, which matters because stored photos are fetched every time they're displayed.
The interface keeps the provider swappable and lets dev/test run without a real bucket.

Objects are private; reads go through short-lived presigned URLs (PRD 11.4: no public
buckets), so we store the object *key* on the row and mint a URL on read.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("health_shared.storage")


@dataclass
class StoredObject:
    key: str
    size: int
    content_type: str


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    def presigned_get_url(self, key: str, expires_in: int = 3600) -> str: ...
    def delete(self, key: str) -> None: ...


class StubStorage:
    """Dev/test storage: keeps bytes in memory and returns a local-looking URL.

    Nothing leaves the process, so meal upload works end to end without an R2 bucket.
    The URL is not actually fetchable; it just lets the flow and tests run.
    """

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self._objects[key] = (data, content_type)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def presigned_get_url(self, key: str, expires_in: int = 3600) -> str:
        return f"/local-object/{key}"

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)


class R2Storage:
    """Cloudflare R2 via the S3-compatible API (boto3)."""

    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str, bucket: str):
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # R2 ignores region but the SDK requires one; "auto" is R2's convention.
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def presigned_get_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


def get_object_storage() -> ObjectStorage:
    """Pick storage from the environment: R2 when fully configured, else the in-memory stub."""
    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket = os.environ.get("R2_BUCKET")
    if account_id and access_key_id and secret and bucket:
        return R2Storage(account_id, access_key_id, secret, bucket)
    logger.warning("object storage not configured (R2_* unset); using in-memory stub")
    return StubStorage()
