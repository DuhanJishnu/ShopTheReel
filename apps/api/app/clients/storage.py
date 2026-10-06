"""ObjectStore interface + MinIO (S3-compatible) implementation + fake for tests.

Uses boto3 (checked against installed boto3 S3 client API: generate_presigned_url,
head_bucket, put_object). No invented APIs.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class ObjectStore(Protocol):
    async def presign_put(self, storage_key: str, content_type: str, expires_s: int = 300) -> str: ...
    async def ensure_bucket(self) -> None: ...
    async def health(self) -> bool: ...


class MinIOStore:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
        )
        self.bucket = settings.s3_bucket

    async def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)

    async def presign_put(self, storage_key: str, content_type: str, expires_s: int = 300) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": storage_key, "ContentType": content_type},
            ExpiresIn=expires_s,
        )

    async def health(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


class FakeStore:
    """In-memory fake for unit tests. Never touches network."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def ensure_bucket(self) -> None:
        return None

    async def presign_put(self, storage_key: str, content_type: str, expires_s: int = 300) -> str:
        self.keys.append(storage_key)
        return f"https://fake-s3/{storage_key}?content-type={content_type}"

    async def health(self) -> bool:
        return True


def new_storage_key(kind: str, content_type: str) -> str:
    ext = {"video/mp4": "mp4", "video/quicktime": "mov", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(
        content_type, "bin"
    )
    prefix = "videos" if kind == "video" else "images"
    return f"{prefix}/{uuid4().hex}.{ext}"


def presign_expiry() -> str:
    return (datetime.now(UTC) + timedelta(seconds=300)).isoformat()
