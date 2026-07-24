"""W2-J · OMA 编辑器增强：Property Editor + Proposals 审查工作流."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str = "p") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #28+#34 Property Editor ───────────────

class PropertyEditor(BaseModel):
    """独立属性编辑器模型 — #28 backing column/title key/TSP + #34 独立编辑器。"""
    id: str = Field(default_factory=lambda: _uid("prop"))
    object_type: str
    name: str
    display_name: str = ""
    description: str = ""
    data_type: str = "string"
    # #28 核心字段
    backing_column: str = ""
    backing_dataset: str = ""
    title_key: bool = False
    is_tsp: bool = False
    tsp_config: dict[str, Any] = Field(default_factory=dict)
    origin: str = "manual"
    origin_mapping: dict[str, Any] = Field(default_factory=dict)
    # 通用元数据
    nullable: bool = True
    indexed: bool = False
    unique: bool = False
    default_value: Any = None
    validation_rules: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class PropertyEditorError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PropertyEditorEngine:
    """属性编辑器引擎（内存存储，不修改 meta_object_type 表）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._props: dict[str, PropertyEditor] = {}

    def create(self, prop: PropertyEditor) -> PropertyEditor:
        with self._lock:
            # 校验 backing_column + backing_dataset 唯一性
            if prop.backing_column and prop.backing_dataset:
                for existing in self._props.values():
                    if (
                        existing.backing_column == prop.backing_column
                        and existing.backing_dataset == prop.backing_dataset
                    ):
                        raise PropertyEditorError(
                            "BACKING_DUPLICATE",
                            f"backing {prop.backing_column}@{prop.backing_dataset} 已被属性 {existing.id} 占用",
                        )
            # 校验 title_key 唯一性（同一 OT 仅一个）
            if prop.title_key:
                for existing in self._props.values():
                    if existing.object_type == prop.object_type and existing.title_key:
                        raise PropertyEditorError(
                            "TITLE_KEY_EXISTS",
                            f"Object Type {prop.object_type} 已有 title key: {existing.name}",
                        )
            # TSP 校验
            if prop.is_tsp and prop.data_type != "timeseries":
                raise PropertyEditorError(
                    "TSP_TYPE_MISMATCH",
                    f"TSP 属性 data_type 必须为 'timeseries'，当前为 '{prop.data_type}'",
                )
            self._props[prop.id] = prop
        return prop

    def get(self, prop_id: str) -> PropertyEditor:
        prop = self._props.get(prop_id)
        if not prop:
            raise PropertyEditorError("NOT_FOUND", f"属性 {prop_id} 不存在")
        return prop

    def list(self, *, object_type: str | None = None) -> list[PropertyEditor]:
        with self._lock:
            props = list(self._props.values())
        if object_type:
            props = [p for p in props if p.object_type == object_type]
        return props

    def update(self, prop_id: str, updates: dict[str, Any]) -> PropertyEditor:
        with self._lock:
            prop = self._props.get(prop_id)
            if not prop:
                raise PropertyEditorError("NOT_FOUND", f"属性 {prop_id} 不存在")
            # title_key 校验
            if updates.get("title_key") and not prop.title_key:
                for existing in self._props.values():
                    if existing.id != prop_id and existing.object_type == prop.object_type and existing.title_key:
                        raise PropertyEditorError(
                            "TITLE_KEY_EXISTS",
                            f"Object Type {prop.object_type} 已有 title key: {existing.name}",
                        )
            # TSP 校验
            if updates.get("is_tsp") and updates.get("data_type", prop.data_type) != "timeseries":
                raise PropertyEditorError(
                    "TSP_TYPE_MISMATCH",
                    "TSP 属性 data_type 必须为 'timeseries'",
                )
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(prop, k, v)
            prop.updated_at = _now()
            return prop

    def delete(self, prop_id: str) -> bool:
        with self._lock:
            if prop_id not in self._props:
                raise PropertyEditorError("NOT_FOUND", f"属性 {prop_id} 不存在")
            del self._props[prop_id]
            return True

    def promote_title_key(self, prop_id: str) -> PropertyEditor:
        with self._lock:
            prop = self._props.get(prop_id)
            if not prop:
                raise PropertyEditorError("NOT_FOUND", f"属性 {prop_id} 不存在")
            # 清除同 OT 下其他 title key
            for existing in self._props.values():
                if existing.object_type == prop.object_type and existing.title_key and existing.id != prop_id:
                    existing.title_key = False
                    existing.updated_at = _now()
            prop.title_key = True
            prop.updated_at = _now()
            return prop

    def get_title_key(self, object_type: str) -> PropertyEditor | None:
        with self._lock:
            for prop in self._props.values():
                if prop.object_type == object_type and prop.title_key:
                    return prop
        return None

    def reset(self) -> None:
        with self._lock:
            self._props.clear()


# ─────────────── #35 Proposals 审查工作流 ───────────────

class ProposalStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    PUBLISHED = "published"


class ProposalComment(BaseModel):
    author: str
    body: str
    action: str = "comment"  # comment / approve / reject / request_changes
    created_at: str = Field(default_factory=_now)


class Proposal(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pp"))
    title: str
    description: str = ""
    branch_id: str
    status: ProposalStatus = ProposalStatus.DRAFT
    author: str = ""
    reviewers: list[str] = Field(default_factory=list)
    comments: list[ProposalComment] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    submitted_at: str | None = None
    reviewed_at: str | None = None
    published_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class ProposalError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# 状态转换表
_TRANSITIONS: dict[ProposalStatus, set[str]] = {
    ProposalStatus.DRAFT: {"submit", "withdraw"},
    ProposalStatus.PENDING_REVIEW: {"start_review", "withdraw"},
    ProposalStatus.IN_REVIEW: {"approve", "reject", "withdraw"},
    ProposalStatus.APPROVED: {"publish"},
    ProposalStatus.REJECTED: {"submit"},
    ProposalStatus.WITHDRAWN: {"submit"},
    ProposalStatus.PUBLISHED: set(),
}


class ProposalEngine:
    """提案审查工作流引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proposals: dict[str, Proposal] = {}

    def create(self, title: str, branch_id: str, *, author: str = "", description: str = "") -> Proposal:
        proposal = Proposal(
            title=title,
            branch_id=branch_id,
            author=author,
            description=description,
        )
        with self._lock:
            self._proposals[proposal.id] = proposal
        return proposal

    def get(self, proposal_id: str) -> Proposal:
        p = self._proposals.get(proposal_id)
        if not p:
            raise ProposalError("NOT_FOUND", f"提案 {proposal_id} 不存在")
        return p

    def list(self, *, status: str | None = None) -> list[Proposal]:
        with self._lock:
            props = list(self._proposals.values())
        if status:
            props = [p for p in props if p.status.value == status]
        return props

    def _transition(self, proposal_id: str, action: str) -> Proposal:
        with self._lock:
            p = self._proposals.get(proposal_id)
            if not p:
                raise ProposalError("NOT_FOUND", f"提案 {proposal_id} 不存在")
            allowed = _TRANSITIONS.get(p.status, set())
            if action not in allowed:
                raise ProposalError(
                    "INVALID_TRANSITION",
                    f"状态 {p.status.value} 不允许操作 {action}（允许: {allowed or '无'}）",
                )
            now = _now()
            if action == "submit":
                p.status = ProposalStatus.PENDING_REVIEW
                p.submitted_at = now
            elif action == "start_review":
                p.status = ProposalStatus.IN_REVIEW
            elif action == "approve":
                p.status = ProposalStatus.APPROVED
                p.reviewed_at = now
            elif action == "reject":
                p.status = ProposalStatus.REJECTED
                p.reviewed_at = now
            elif action == "withdraw":
                p.status = ProposalStatus.WITHDRAWN
            elif action == "publish":
                p.status = ProposalStatus.PUBLISHED
                p.published_at = now
            p.updated_at = now
            return p

    def submit(self, proposal_id: str) -> Proposal:
        return self._transition(proposal_id, "submit")

    def start_review(self, proposal_id: str) -> Proposal:
        return self._transition(proposal_id, "start_review")

    def approve(self, proposal_id: str) -> Proposal:
        return self._transition(proposal_id, "approve")

    def reject(self, proposal_id: str) -> Proposal:
        return self._transition(proposal_id, "reject")

    def withdraw(self, proposal_id: str) -> Proposal:
        return self._transition(proposal_id, "withdraw")

    def publish(self, proposal_id: str) -> Proposal:
        return self._transition(proposal_id, "publish")

    def add_comment(self, proposal_id: str, comment: ProposalComment) -> Proposal:
        with self._lock:
            p = self._proposals.get(proposal_id)
            if not p:
                raise ProposalError("NOT_FOUND", f"提案 {proposal_id} 不存在")
            p.comments.append(comment)
            p.updated_at = _now()
            return p

    def add_reviewer(self, proposal_id: str, reviewer: str) -> Proposal:
        with self._lock:
            p = self._proposals.get(proposal_id)
            if not p:
                raise ProposalError("NOT_FOUND", f"提案 {proposal_id} 不存在")
            if reviewer not in p.reviewers:
                p.reviewers.append(reviewer)
            p.updated_at = _now()
            return p

    def reset(self) -> None:
        with self._lock:
            self._proposals.clear()


# ─────────────── 单例 ───────────────

_prop_engine: PropertyEditorEngine | None = None
_proposal_engine: ProposalEngine | None = None
_singleton_lock = threading.Lock()


def get_property_engine() -> PropertyEditorEngine:
    global _prop_engine
    if _prop_engine is None:
        with _singleton_lock:
            if _prop_engine is None:
                _prop_engine = PropertyEditorEngine()
    return _prop_engine


def get_proposal_engine() -> ProposalEngine:
    global _proposal_engine
    if _proposal_engine is None:
        with _singleton_lock:
            if _proposal_engine is None:
                _proposal_engine = ProposalEngine()
    return _proposal_engine
