"W4 · Sync 故障排除（220w L292） 测试."""
from __future__ import annotations

import pytest

from aos_api.dc_sync_troubleshoot import (
    SyncTroubleshoot,
    SyncTroubleshootEngine,
    SyncTroubleshootError,
    get_engine,
)


class TestSyncTroubleshootEngine:
    def setup_method(self) -> None:
        self.eng = SyncTroubleshootEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> SyncTroubleshoot:
        return SyncTroubleshoot(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "st_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "st_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(SyncTroubleshootError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "st_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(SyncTroubleshootError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "st_id"))
        with pytest.raises(SyncTroubleshootError):
            self.eng.get(getattr(item, "st_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestSyncTroubleshootSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
