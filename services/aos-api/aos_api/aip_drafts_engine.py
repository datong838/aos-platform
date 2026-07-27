"""Phase 3 · AIP Drafts 引擎.

Draft 审查任务（状态机 draft→approved/rejected）。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["approved", "rejected"],
    "approved": [],
    "rejected": ["draft"],
}


class DraftReview(BaseModel):
    id: str = Field(default_factory=lambda: "aip-draft-" + uuid.uuid4().hex[:8])
    title: str = ""
    draft_type: str = "report"  # report | config | code | pipeline
    author: str = ""
    reviewer: str = ""
    status: str = "draft"  # draft → approved | rejected
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())
    reviewed_at: float | None = None


class DraftsEngine:
    """AIP Drafts 引擎。"""

    _instance: "DraftsEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "DraftsEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._drafts: dict[str, DraftReview] = {}
        return cls._instance

    def create(self, title: str, **kwargs: Any) -> DraftReview:
        with _LOCK:
            draft = DraftReview(title=title, **kwargs)
            self._drafts[draft.id] = draft
            return draft

    def get(self, draft_id: str) -> DraftReview | None:
        return self._drafts.get(draft_id)

    def list(self, status: str | None = None, draft_type: str | None = None) -> list[DraftReview]:
        items = list(self._drafts.values())
        if status:
            items = [d for d in items if d.status == status]
        if draft_type:
            items = [d for d in items if d.draft_type == draft_type]
        return items

    def update(self, draft_id: str, **kwargs: Any) -> DraftReview:
        with _LOCK:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"Draft {draft_id} not found")
            for k, v in kwargs.items():
                if hasattr(draft, k):
                    setattr(draft, k, v)
            draft.updated_at = time.time()
            return draft

    def approve(self, draft_id: str, reviewer: str = "") -> DraftReview:
        with _LOCK:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"Draft {draft_id} not found")
            if draft.status not in VALID_TRANSITIONS or "approved" not in VALID_TRANSITIONS.get(draft.status, []):
                raise ValueError(f"Cannot approve draft in status '{draft.status}'")
            draft.status = "approved"
            draft.reviewer = reviewer or draft.reviewer
            draft.reviewed_at = time.time()
            draft.updated_at = time.time()
            return draft

    def reject(self, draft_id: str, reviewer: str = "", reason: str = "") -> DraftReview:
        with _LOCK:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"Draft {draft_id} not found")
            if "rejected" not in VALID_TRANSITIONS.get(draft.status, []):
                raise ValueError(f"Cannot reject draft in status '{draft.status}'")
            draft.status = "rejected"
            draft.reviewer = reviewer or draft.reviewer
            draft.metadata["reject_reason"] = reason
            draft.reviewed_at = time.time()
            draft.updated_at = time.time()
            return draft

    def reopen(self, draft_id: str) -> DraftReview:
        with _LOCK:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"Draft {draft_id} not found")
            if "draft" not in VALID_TRANSITIONS.get(draft.status, []):
                raise ValueError(f"Cannot reopen draft in status '{draft.status}'")
            draft.status = "draft"
            draft.reviewed_at = None
            draft.updated_at = time.time()
            return draft

    def delete(self, draft_id: str) -> bool:
        with _LOCK:
            return self._drafts.pop(draft_id, None) is not None

    def stats(self) -> dict[str, Any]:
        items = list(self._drafts.values())
        by_status: dict[str, int] = {}
        for d in items:
            by_status[d.status] = by_status.get(d.status, 0) + 1
        return {"total": len(items), "by_status": by_status}

    def reset(self) -> None:
        with _LOCK:
            self._drafts.clear()


def get_engine() -> DraftsEngine:
    return DraftsEngine()
