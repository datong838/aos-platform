"""Deterministic result-feedback plan after an exact content review Receipt."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any

from .content_artifact_review import ContentReviewReceipt, ReadableContentArtifact
from .ecommerce_business_investigation_review_command import exact_ref_payload
from .sdk_ports import ExactRef


_TECHNICAL_TEXT = re.compile(
    r"(?:(?:AR|W|R|N)\s*[-_]?\s*\d|技术方案|开发任务|波次|API|SQL|DDL|数据库迁移|"
    r"(?:Artifact|Receipt|TaskBrief|Operation|Provider|Usage)[A-Za-z]*|sha256:|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b|"
    r"(?:/[\w.-]+){2,}|(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|sql|md|json|ya?ml))",
    re.IGNORECASE,
)
_KINDS_BY_DECISION = {
    "ACCEPT": ("daily_review", "improvement_observation", "memory_candidate"),
    "RETURN": ("content_return_target",),
}
_TITLES = {
    "daily_review": "今日内容复盘",
    "improvement_observation": "内容效果改进建议",
    "memory_candidate": "内容经验候选",
    "content_return_target": "内容方案重新调整",
}


def _business_text(value: Any, *, name: str, limit: int) -> str:
    if type(value) is not str or not 1 <= len(value.strip()) <= limit:
        raise ValueError(f"{name} must be non-empty bounded business text")
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKC", value)
        if unicodedata.category(character) != "Cf"
    )
    if not re.search(r"[\u3400-\u9fff]", normalized) or _TECHNICAL_TEXT.search(normalized):
        raise ValueError(f"{name} contains non-business technical text")
    return value.strip()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FeedbackSegment:
    sequence: int
    kind: str
    target_id: str
    business_title: str
    business_summary: str
    target_phase: str | None = None

    def payload(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "targetId": self.target_id,
            "businessTitle": self.business_title,
            "businessSummary": self.business_summary,
            "targetPhase": self.target_phase,
        }


@dataclass(frozen=True, slots=True)
class ResultFeedbackPlan:
    command_id: str
    command_hash: str
    decision: str
    review_receipt_ref: ExactRef
    artifact_ref: ExactRef
    task_ref: ExactRef
    brief_ref: ExactRef
    segments: tuple[FeedbackSegment, ...]

    def payload(self) -> dict[str, object]:
        return {
            "commandId": self.command_id,
            "requestHash": f"sha256:{self.command_hash}",
            "decision": self.decision,
            "reviewReceiptRef": exact_ref_payload(self.review_receipt_ref),
            "artifactRef": exact_ref_payload(self.artifact_ref),
            "taskRef": exact_ref_payload(self.task_ref),
            "briefRef": exact_ref_payload(self.brief_ref),
            "segments": [segment.payload() for segment in self.segments],
            "sideEffects": {
                "providerInvocationCount": 0,
                "externalPublicationCount": 0,
                "externalBusinessMutationCount": 0,
                "taskCreatedCount": 0,
                "budgetSettlementCount": 0,
            },
        }


@dataclass(frozen=True, slots=True)
class ResultFeedbackRequest:
    review_receipt: ContentReviewReceipt
    artifact: ReadableContentArtifact
    business_task_title: str
    artifact_summary: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.review_receipt.decision not in _KINDS_BY_DECISION:
            raise ValueError("unsupported content-review decision for feedback")
        if (
            self.review_receipt.artifact_ref != self.artifact.artifact_ref
            or self.review_receipt.task_ref != self.artifact.task_ref
            or self.review_receipt.brief_ref != self.artifact.brief_ref
        ):
            raise ValueError("feedback exact lineage drifted")
        if self.review_receipt.decision == "RETURN" and self.review_receipt.return_stage != "content_generation":
            raise ValueError("RETURN feedback must target content_generation")
        if self.review_receipt.decision == "ACCEPT" and self.review_receipt.return_stage is not None:
            raise ValueError("ACCEPT feedback cannot contain a return stage")
        _business_text(self.business_task_title, name="business_task_title", limit=120)
        _business_text(self.artifact_summary, name="artifact_summary", limit=500)
        if type(self.idempotency_key) is not str or not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("feedback idempotency key is required and bounded")


def build_result_feedback(request: ResultFeedbackRequest) -> ResultFeedbackPlan:
    identity = {
        "reviewReceiptRef": exact_ref_payload(request.review_receipt.receipt_ref),
        "decision": request.review_receipt.decision,
        "artifactRef": exact_ref_payload(request.artifact.artifact_ref),
        "taskRef": exact_ref_payload(request.artifact.task_ref),
        "briefRef": exact_ref_payload(request.artifact.brief_ref),
        "businessTaskTitle": request.business_task_title.strip(),
        "artifactSummary": request.artifact_summary.strip(),
        "idempotencyKey": request.idempotency_key.strip(),
    }
    command_hash = _stable_hash(identity)
    command_id = f"feedback-{command_hash[:40]}"
    summaries = {
        "daily_review": f"{request.business_task_title}的内容已通过评审，等待后续效果观察。",
        "improvement_observation": f"{request.business_task_title}暂无足够证据判断效果，需要积累可比较的业务结果。",
        "memory_candidate": f"{request.business_task_title}形成一条待治理的经验候选，尚未进入知识库。",
        "content_return_target": f"{request.business_task_title}需要根据评审意见重新调整内容，原内容保留不变。",
    }
    segments = tuple(
        FeedbackSegment(
            sequence=index,
            kind=kind,
            target_id=f"{kind}-{_stable_hash({'commandId': command_id, 'kind': kind})[:40]}",
            business_title=_TITLES[kind],
            business_summary=_business_text(summaries[kind], name="business_summary", limit=500),
            target_phase="content_generation" if kind == "content_return_target" else None,
        )
        for index, kind in enumerate(_KINDS_BY_DECISION[request.review_receipt.decision], start=1)
    )
    return ResultFeedbackPlan(
        command_id=command_id,
        command_hash=command_hash,
        decision=request.review_receipt.decision,
        review_receipt_ref=request.review_receipt.receipt_ref,
        artifact_ref=request.artifact.artifact_ref,
        task_ref=request.artifact.task_ref,
        brief_ref=request.artifact.brief_ref,
        segments=segments,
    )


__all__ = [
    "FeedbackSegment",
    "ResultFeedbackPlan",
    "ResultFeedbackRequest",
    "build_result_feedback",
]
