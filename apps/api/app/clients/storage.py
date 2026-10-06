"""ObjectStore interface + S3-compatible implementation + fake for tests.

Local dev runs LocalStack S3 (see docker-compose.yml); prod may use MinIO or any
S3. Uses boto3 (checked against installed boto3 S3 client API:
generate_presigned_url, head_bucket, put_object) with path-style addressing so
custom endpoints resolve inside Docker networks. No invented APIs.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

import boto3
from botocore.config import Config
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
    async def presign_get(self, storage_key: str, expires_s: int = 300) -> str: ...
    async def put_bytes(self, storage_key: str, data: bytes, content_type: str) -> None: ...
    async def download_bytes(self, storage_key: str) -> bytes: ...
    async def ensure_bucket(self) -> None: ...
    async def health(self) -> bool: ...


class MinIOStore:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(s3={"addressing_style": "path"}),
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

    async def presign_get(self, storage_key: str, expires_s: int = 300) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=expires_s,
        )

    async def put_bytes(self, storage_key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=storage_key, Body=data, ContentType=content_type)

    async def download_bytes(self, storage_key: str) -> bytes:
        obj = self._client.get_object(Bucket=self.bucket, Key=storage_key)
        return obj["Body"].read()

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
        self.blobs: dict[str, bytes] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def presign_put(self, storage_key: str, content_type: str, expires_s: int = 300) -> str:
        self.keys.append(storage_key)
        return f"https://fake-s3/{storage_key}?content-type={content_type}"

    async def presign_get(self, storage_key: str, expires_s: int = 300) -> str:
        return f"https://fake-s3/{storage_key}"

    async def put_bytes(self, storage_key: str, data: bytes, content_type: str) -> None:
        self.keys.append(storage_key)
        self.blobs[storage_key] = data

    async def download_bytes(self, storage_key: str) -> bytes:
        return self.blobs[storage_key]

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
