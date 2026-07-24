"""W1-9 · MediaReference Bridge。

媒体引用（不存数据本身）+ S3/本地双适配 + 签名直链 + 缩略图占位 + 权限继承标记。

详见 docs/palantier/20_tech/220tech_media-reference.md。
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "mr-" + uuid.uuid4().hex[:12]


class MediaReference(BaseModel):
    id: str
    kind: Literal["image", "video", "audio", "document"] = "document"
    storage: Literal["s3", "local"] = "local"
    bucket: str
    path: str
    version: str = "1"
    mime: str = ""
    size_bytes: int = 0
    thumbnails: dict[str, str] = Field(default_factory=dict)
    owner_object_type: str = ""
    owner_object_id: str = ""
    created_at: str = Field(default_factory=_now)


class MediaStorageAdapter(Protocol):
    def exists(self, bucket: str, path: str) -> bool: ...
    def signed_url(self, bucket: str, path: str, expires_seconds: int = 3600) -> str: ...
    def read_bytes(self, bucket: str, path: str, max_bytes: int = 10485760) -> bytes: ...


class LocalAdapter:
    def __init__(self, base_dir: str = "/tmp/aos_media") -> None:
        self._base = base_dir

    def _full(self, bucket: str, path: str) -> str:
        return os.path.join(self._base, bucket, path)

    def exists(self, bucket: str, path: str) -> bool:
        return os.path.exists(self._full(bucket, path))

    def signed_url(self, bucket: str, path: str, expires_seconds: int = 3600) -> str:
        token = uuid.uuid4().hex[:8]
        expiry_ts = int(datetime.now(timezone.utc).timestamp()) + expires_seconds
        return f"file://{self._full(bucket, path)}?token={token}&expires={expiry_ts}"

    def read_bytes(self, bucket: str, path: str, max_bytes: int = 10485760) -> bytes:
        full = self._full(bucket, path)
        if not os.path.exists(full):
            return b""
        with open(full, "rb") as fh:
            return fh.read(max_bytes)


class S3MockAdapter:
    def __init__(self, endpoint: str = "https://s3.mock.local") -> None:
        self._endpoint = endpoint

    def exists(self, bucket: str, path: str) -> bool:
        return True

    def signed_url(self, bucket: str, path: str, expires_seconds: int = 3600) -> str:
        token = uuid.uuid4().hex[:8]
        expiry_ts = int(datetime.now(timezone.utc).timestamp()) + expires_seconds
        return f"{self._endpoint}/{bucket}/{path}?X-Amz-Signature={token}&Expires={expiry_ts}"

    def read_bytes(self, bucket: str, path: str, max_bytes: int = 10485760) -> bytes:
        return b""


class MediaReferenceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MediaReferenceStore:
    def __init__(self) -> None:
        self._refs: dict[str, MediaReference] = {}
        self._adapters: dict[str, MediaStorageAdapter] = {
            "local": LocalAdapter(),
            "s3": S3MockAdapter(),
        }
        self._lock = threading.Lock()

    def set_adapter(self, storage_kind: str, adapter: MediaStorageAdapter) -> None:
        with self._lock:
            self._adapters[storage_kind] = adapter

    def register(
        self,
        kind: str,
        storage: str,
        bucket: str,
        path: str,
        mime: str = "",
        size_bytes: int = 0,
        owner_object_type: str = "",
        owner_object_id: str = "",
    ) -> MediaReference:
        if storage not in self._adapters:
            raise MediaReferenceError("BAD_STORAGE", f"未知 storage {storage!r}")
        if not bucket or not path:
            raise MediaReferenceError("BAD_PATH", "bucket 和 path 不能为空")
        ref = MediaReference(
            id=_new_id(), kind=kind, storage=storage, bucket=bucket, path=path,
            mime=mime, size_bytes=size_bytes,
            owner_object_type=owner_object_type, owner_object_id=owner_object_id,
        )
        with self._lock:
            self._refs[ref.id] = ref
        return ref

    def get(self, ref_id: str) -> MediaReference:
        if ref_id not in self._refs:
            raise MediaReferenceError("NOT_FOUND", f"MediaReference {ref_id!r} 不存在")
        return self._refs[ref_id]

    def list_all(self) -> list[MediaReference]:
        return list(self._refs.values())

    def delete(self, ref_id: str) -> None:
        with self._lock:
            if ref_id not in self._refs:
                raise MediaReferenceError("NOT_FOUND", f"MediaReference {ref_id!r} 不存在")
            del self._refs[ref_id]

    def get_signed_url(self, ref_id: str, expires_seconds: int = 3600) -> str:
        ref = self.get(ref_id)
        adapter = self._adapters[ref.storage]
        return adapter.signed_url(ref.bucket, ref.path, expires_seconds)

    def generate_thumbnail(self, ref_id: str, sizes: list[str] | None = None) -> dict[str, str]:
        ref = self.get(ref_id)
        if ref.kind not in {"image", "video"}:
            raise MediaReferenceError("BAD_KIND", f"kind {ref.kind!r} 不支持缩略图")
        sizes = sizes or ["small", "medium", "large"]
        base = ref.path.rsplit(".", 1)[0]
        result: dict[str, str] = {}
        for size in sizes:
            result[size] = f"/thumbnails/{ref.id}/{base}_{size}.webp"
        with self._lock:
            self._refs[ref_id] = ref.model_copy(update={"thumbnails": {**ref.thumbnails, **result}})
        return result

    def list_by_owner(self, object_type: str, object_id: str) -> list[MediaReference]:
        return [
            r for r in self._refs.values()
            if r.owner_object_type == object_type and r.owner_object_id == object_id
        ]


_store = MediaReferenceStore()


def get_store() -> MediaReferenceStore:
    return _store
