"""Phase 3 · AIP Drafts 引擎.

Draft 审查任务（状态机对齐前端 DraftInbox）：
  draft → submitted → in_review → approved | rejected | changes_requested
  draft|submitted → withdrawn；changes_requested → draft；rejected → draft (reopen)

兼容捷径（既有单测）：draft → approved | rejected。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()

# 与前端 TRANSITIONS 对齐；额外保留 draft→approved/rejected 兼容旧测
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted", "withdrawn", "approved", "rejected"],
    "submitted": ["in_review", "withdrawn"],
    "in_review": ["approved", "rejected", "changes_requested"],
    "approved": [],
    "rejected": ["draft"],
    "withdrawn": [],
    "changes_requested": ["draft"],
}

_STATUS_TO_ACTION: dict[str, str] = {
    "draft": "create",
    "submitted": "submit",
    "in_review": "in_review",
    "approved": "approve",
    "rejected": "reject",
    "withdrawn": "withdraw",
    "changes_requested": "changes_requested",
}


def _now() -> float:
    return time.time()


def _iso(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts if ts is not None else _now()))


def _timeline_entry(
    action: str,
    actor: str = "",
    comment: str = "",
    ts: float | None = None,
) -> dict[str, Any]:
    return {
        "id": "tl-" + uuid.uuid4().hex[:8],
        "action": action,
        "actor": actor or "system",
        "timestamp": _iso(ts),
        "comment": comment or None,
    }


class DraftReview(BaseModel):
    id: str = Field(default_factory=lambda: "aip-draft-" + uuid.uuid4().hex[:8])
    title: str = ""
    draft_type: str = "report"  # report | config | code | pipeline | Action | ...
    author: str = ""
    reviewer: str = ""
    status: str = "draft"
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=_now)
    updated_at: float = Field(default_factory=_now)
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
            timeline = list(kwargs.pop("timeline", []) or [])
            author = str(kwargs.get("author") or "")
            if not timeline:
                timeline = [_timeline_entry("create", actor=author or "system")]
            draft = DraftReview(title=title, timeline=timeline, **kwargs)
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
            draft.updated_at = _now()
            return draft

    def _assert_transition(self, draft: DraftReview, to: str) -> None:
        allowed = VALID_TRANSITIONS.get(draft.status, [])
        if to not in allowed:
            raise ValueError(f"Cannot transition draft from '{draft.status}' to '{to}'")

    def transition(
        self,
        draft_id: str,
        to: str,
        *,
        actor: str = "",
        comment: str = "",
    ) -> DraftReview:
        with _LOCK:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"Draft {draft_id} not found")
            self._assert_transition(draft, to)
            action = _STATUS_TO_ACTION.get(to, to)
            draft.status = to
            draft.updated_at = _now()
            if to in ("approved", "rejected"):
                draft.reviewed_at = draft.updated_at
                if actor:
                    draft.reviewer = actor
            if to == "rejected" and comment:
                draft.metadata["reject_reason"] = comment
            if to == "draft":
                draft.reviewed_at = None
            draft.timeline = [
                *draft.timeline,
                _timeline_entry(action, actor=actor or draft.reviewer or draft.author, comment=comment),
            ]
            return draft

    def approve(self, draft_id: str, reviewer: str = "") -> DraftReview:
        with _LOCK:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"Draft {draft_id} not found")
            if "approved" not in VALID_TRANSITIONS.get(draft.status, []):
                raise ValueError(f"Cannot approve draft in status '{draft.status}'")
            draft.status = "approved"
            draft.reviewer = reviewer or draft.reviewer
            draft.reviewed_at = _now()
            draft.updated_at = draft.reviewed_at
            draft.timeline = [
                *draft.timeline,
                _timeline_entry("approve", actor=draft.reviewer or "reviewer"),
            ]
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
            draft.reviewed_at = _now()
            draft.updated_at = draft.reviewed_at
            draft.timeline = [
                *draft.timeline,
                _timeline_entry("reject", actor=draft.reviewer or "reviewer", comment=reason),
            ]
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
            draft.updated_at = _now()
            draft.timeline = [
                *draft.timeline,
                _timeline_entry("create", actor=draft.author or "system", comment="reopened"),
            ]
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


def draft_to_api_dict(draft: DraftReview) -> dict[str, Any]:
    """Snake + camelCase 双写，便于前端 / SDK 消费。"""
    raw = draft.model_dump()
    return {
        **raw,
        "draftType": draft.draft_type,
        "createdBy": draft.author,
        "createdAt": _iso(draft.created_at),
        "updatedAt": _iso(draft.updated_at),
        "reviewedAt": _iso(draft.reviewed_at) if draft.reviewed_at is not None else None,
        "summary": draft.content,
        "type": draft.draft_type,
        "submittedBy": draft.author,
    }
