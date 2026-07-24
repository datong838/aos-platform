"""W3 Task 6.2 · 流水线审查（220w L1824）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class PipelineReviewError(Exception):
    """流水线审查错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PipelineReview(BaseModel):
    """流水线审查（220w L1824）."""
    pr_id: str = ""
    pipeline_id: str = ""
    commit_sha: str = ""
    review_status: str = "PENDING"
    reviewer: str = ""
    review_comments: list[dict] = []  # 审查评论
    lint_results: dict = {}  # Lint 结果
    test_results: dict = {}  # 测试结果
    build_status: str = "UNKNOWN"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PipelineReviewEngine:
    """流水线审查（220w L1824）."""

    _instance: Optional[PipelineReviewEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, PipelineReview] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "PipelineReviewEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: PipelineReview) -> PipelineReview:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"pr-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "pr_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "pr_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> PipelineReview:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise PipelineReviewError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[PipelineReview]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> PipelineReview:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise PipelineReviewError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise PipelineReviewError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def submit(self, pipeline_id, commit_sha) -> dict:
        """提交审查."""
        return {"ok": True, "method": "submit"}

    def approve(self, review_id, reviewer) -> dict:
        """批准."""
        return {"ok": True, "method": "approve"}

    def reject(self, review_id, reviewer, reason) -> dict:
        """拒绝."""
        return {"ok": True, "method": "reject"}

    def add_comment(self, review_id, comment) -> dict:
        """添加评论."""
        return {"ok": True, "method": "add_comment"}


def get_engine() -> PipelineReviewEngine:
    return PipelineReviewEngine.get_instance()
