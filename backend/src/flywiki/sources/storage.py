import asyncio
import hashlib
import io
from dataclasses import dataclass
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from flywiki.config import Settings


class ObjectCollisionError(RuntimeError):
    """The key exists but does not contain the expected immutable bytes."""


class ObjectStore(Protocol):
    async def put_if_absent(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        content_sha256: str,
    ) -> None: ...

    async def get(self, key: str) -> bytes: ...


@dataclass(frozen=True)
class StoredObject:
    content: bytes
    content_type: str
    content_sha256: str


class InMemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}

    async def put_if_absent(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        content_sha256: str,
    ) -> None:
        existing = self.objects.get(key)
        if existing is not None:
            if existing.content_sha256 != content_sha256 or existing.content != content:
                raise ObjectCollisionError(f"object key collision: {key}")
            return
        if hashlib.sha256(content).hexdigest() != content_sha256:
            raise ValueError("content_sha256 does not match content")
        self.objects[key] = StoredObject(content, content_type, content_sha256)

    async def get(self, key: str) -> bytes:
        return self.objects[key].content


class MinioObjectStore:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def put_if_absent(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        content_sha256: str,
    ) -> None:
        if hashlib.sha256(content).hexdigest() != content_sha256:
            raise ValueError("content_sha256 does not match content")
        await asyncio.to_thread(
            self._put_if_absent_sync,
            key,
            content,
            content_type,
            content_sha256,
        )

    def _put_if_absent_sync(
        self,
        key: str,
        content: bytes,
        content_type: str,
        content_sha256: str,
    ) -> None:
        try:
            existing = self._client.stat_object(self._bucket, key)
        except S3Error as exc:
            if exc.code not in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise
        else:
            metadata = {key.lower(): value for key, value in existing.metadata.items()}
            stored_sha256 = metadata.get("x-amz-meta-content-sha256")
            if stored_sha256 != content_sha256 or existing.size != len(content):
                raise ObjectCollisionError(f"object key collision: {key}")
            return

        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(content),
            length=len(content),
            content_type=content_type,
            metadata={"content-sha256": content_sha256},
        )

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, key)

    def _get_sync(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


def create_minio_object_store(settings: Settings) -> MinioObjectStore:
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    return MinioObjectStore(client, settings.source_bucket)
