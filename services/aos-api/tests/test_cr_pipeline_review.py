"""W3 Task 6.2 · 流水线审查（220w L1824） 测试."""
from __future__ import annotations

import pytest

from aos_api.cr_pipeline_review import (
    PipelineReview,
    PipelineReviewEngine,
    PipelineReviewError,
    get_engine,
)


class TestPipelineReviewEngine:
    def setup_method(self) -> None:
        self.eng = PipelineReviewEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> PipelineReview:
        defaults: dict = {}
        return PipelineReview(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "pr_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "pr_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(PipelineReviewError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "pr_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(PipelineReviewError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "pr_id"))
        with pytest.raises(PipelineReviewError):
            self.eng.get(getattr(item, "pr_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestPipelineReviewEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
