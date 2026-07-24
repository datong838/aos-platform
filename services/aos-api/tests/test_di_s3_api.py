"W4 · S3 API 协议暴露（220w L930） 测试."""
from __future__ import annotations

import pytest

from aos_api.di_s3_api import (
    S3Api,
    S3ApiEngine,
    S3ApiError,
    get_engine,
)


class TestS3ApiEngine:
    def setup_method(self) -> None:
        self.eng = S3ApiEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> S3Api:
        return S3Api(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "s3a_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "s3a_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(S3ApiError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "s3a_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(S3ApiError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "s3a_id"))
        with pytest.raises(S3ApiError):
            self.eng.get(getattr(item, "s3a_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestS3ApiSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
