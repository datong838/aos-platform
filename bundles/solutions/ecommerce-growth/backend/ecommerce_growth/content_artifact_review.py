"""Readable content Artifact and exact content-review package contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from aos_extension_sdk import DispatchRef, commit_with_dispatch

from .aip_business_investigation_compiler import canonical_command_hash
from .ecommerce_business_investigation_review_command import (
    exact_ref_from_payload,
    exact_ref_payload,
)
from .sdk_ports import ExactRef, GrowthContentReviewPort


CONTENT_REVIEW_OPERATION = "ecommerce_growth_content_review"
_TECHNICAL_TEXT = re.compile(
    r"(?:(?:AR|W|R|N)\s*[-_]?\s*\d|技术方案|开发任务|波次|API|SQL|DDL|数据库迁移|代码|(?:Artifact|Dataset|DataFulfillment|EvidenceBundle|TaskBrief|GrowthPlan|Capability|Provider|Usage|Installation)[A-Za-z]*(?:Revision|Receipt)|sha256\s*:|\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b|(?:/[\w.-]+){2,}|(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|sql|md|json|ya?ml)|\b[\w.-]+\.(?:py|ts|tsx|js|sql|md|json|ya?ml)\b|[A-Za-z]:\\+[^\\\s]+(?:\\+[^\\\s]+)+)",
    re.IGNORECASE,
)
_ARTIFACT_FIELDS = frozenset(
    {
        "artifactRef",
        "taskRef",
        "briefRef",
        "growthPlanRef",
        "sourceArtifactRefs",
        "productNames",
        "channels",
        "factSourceRefs",
        "body",
        "constraintChecks",
    }
)
_REVIEW_RECEIPT_FIELDS = frozenset(
    {
        "receiptRef",
        "requestHash",
        "decision",
        "artifactRef",
        "taskRef",
        "briefRef",
        "reviewIssueRef",
        "reviewerAuthorityRef",
        "returnStage",
        "replayed",
        "sideEffects",
    }
)
_REVIEW_SIDE_EFFECT_FIELDS = frozenset(
    {"externalPublicationCount", "externalBusinessMutationCount"}
)


def validated_business_text(value: Any, *, name: str, limit: int) -> str:
    if type(value) is not str or not 1 <= len(value.strip()) <= limit:
        raise ValueError(f"{name} must be non-empty bounded business text")
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKC", value)
        if unicodedata.category(character) != "Cf"
    )
    if not re.search(r"[\u3400-\u9fff]", normalized) or _TECHNICAL_TEXT.search(normalized):
        raise ValueError(f"{name} contains non-business technical text")
    return value


def _string_tuple(value: Any, *, name: str, maximum: int) -> tuple[str, ...]:
    if type(value) is not list or not 1 <= len(value) <= maximum:
        raise ValueError(f"{name} must be a bounded non-empty list")
    result = tuple(validated_business_text(item, name=name, limit=300) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} values must be unique")
    return result


def _exact_ref_tuple(value: Any, *, name: str, kinds: set[str], maximum: int) -> tuple[ExactRef, ...]:
    if type(value) is not list or not 1 <= len(value) <= maximum:
        raise ValueError(f"{name} must be a bounded non-empty exact-ref list")
    result = tuple(exact_ref_from_payload(item, kinds) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} exact refs must be unique")
    return result


@dataclass(frozen=True, slots=True)
class ReadableContentArtifact:
    artifact_ref: ExactRef
    task_ref: ExactRef
    brief_ref: ExactRef
    growth_plan_ref: ExactRef
    source_artifact_refs: tuple[ExactRef, ...]
    product_names: tuple[str, ...]
    channels: tuple[str, ...]
    fact_source_refs: tuple[ExactRef, ...]
    body: str
    constraint_checks: tuple[str, ...]

    @classmethod
    def from_payload(cls, value: Any) -> "ReadableContentArtifact":
        if type(value) is not dict or set(value) != _ARTIFACT_FIELDS:
            raise ValueError("content Artifact fields drifted")
        artifact = cls(
            artifact_ref=exact_ref_from_payload(value["artifactRef"], {"ArtifactRevision"}),
            task_ref=exact_ref_from_payload(value["taskRef"], {"Task"}),
            brief_ref=exact_ref_from_payload(value["briefRef"], {"TaskBriefRevision"}),
            growth_plan_ref=exact_ref_from_payload(
                value["growthPlanRef"], {"GrowthPlanRevision"}
            ),
            source_artifact_refs=_exact_ref_tuple(
                value["sourceArtifactRefs"],
                name="sourceArtifactRefs",
                kinds={"ArtifactRevision"},
                maximum=16,
            ),
            product_names=_string_tuple(
                value["productNames"], name="productNames", maximum=50
            ),
            channels=_string_tuple(value["channels"], name="channels", maximum=12),
            fact_source_refs=_exact_ref_tuple(
                value["factSourceRefs"],
                name="factSourceRefs",
                kinds={
                    "EvidenceBundleRevision",
                    "DatasetRevision",
                    "DataFulfillmentReceipt",
                },
                maximum=200,
            ),
            body=validated_business_text(value["body"], name="body", limit=20_000),
            constraint_checks=_string_tuple(
                value["constraintChecks"], name="constraintChecks", maximum=50
            ),
        )
        if len(artifact.source_artifact_refs) != 4:
            raise ValueError("content Artifact requires four source Artifacts")
        return artifact


@dataclass(frozen=True, slots=True)
class ContentReviewRequest:
    artifact: ReadableContentArtifact
    review_issue_ref: ExactRef
    reviewer_authority_ref: ExactRef
    decision: str
    idempotency_key: str
    return_stage: str | None = None

    def __post_init__(self) -> None:
        if self.review_issue_ref.resource_type != "ReviewIssueRevision":
            raise ValueError("content review requires ReviewIssueRevision")
        if self.reviewer_authority_ref.resource_type != "ReviewerAuthorityRevision":
            raise ValueError("content review requires ReviewerAuthorityRevision")
        if type(self.idempotency_key) is not str or not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("content review idempotency key is required and bounded")
        if self.decision == "REQUEST_MORE":
            raise ValueError("REQUEST_MORE has no canonical content-review authority")
        if self.decision == "ACCEPT":
            if self.return_stage is not None:
                raise ValueError("ACCEPT cannot contain returnStage")
        elif self.decision == "RETURN":
            if self.return_stage != "content_generation":
                raise ValueError("RETURN must target content_generation")
        else:
            raise ValueError("unsupported content-review decision")

    def command_payload(self) -> dict[str, object]:
        artifact = self.artifact
        return {
            "operation": "content.review",
            "artifactRef": exact_ref_payload(artifact.artifact_ref),
            "taskRef": exact_ref_payload(artifact.task_ref),
            "briefRef": exact_ref_payload(artifact.brief_ref),
            "growthPlanRef": exact_ref_payload(artifact.growth_plan_ref),
            "sourceArtifactRefs": [exact_ref_payload(ref) for ref in artifact.source_artifact_refs],
            "reviewIssueRef": exact_ref_payload(self.review_issue_ref),
            "reviewerAuthorityRef": exact_ref_payload(self.reviewer_authority_ref),
            "artifactContentHash": artifact.artifact_ref.content_hash,
            "decision": self.decision,
            "returnStage": self.return_stage,
            "idempotencyKey": self.idempotency_key,
        }


@dataclass(frozen=True, slots=True)
class ContentReviewReceipt:
    receipt_ref: ExactRef
    request_hash: str
    decision: str
    artifact_ref: ExactRef
    task_ref: ExactRef
    brief_ref: ExactRef
    review_issue_ref: ExactRef
    reviewer_authority_ref: ExactRef
    return_stage: str | None
    replayed: bool

    @classmethod
    def from_payload(
        cls, value: Any, *, request: ContentReviewRequest, request_hash: str
    ) -> "ContentReviewReceipt":
        if type(value) is not dict or set(value) != _REVIEW_RECEIPT_FIELDS:
            raise ValueError("content review Receipt fields drifted")
        effects = value["sideEffects"]
        if (
            type(effects) is not dict
            or set(effects) != _REVIEW_SIDE_EFFECT_FIELDS
            or any(type(effects[field]) is not int or effects[field] != 0 for field in effects)
        ):
            raise ValueError("content review external side-effect boundary drifted")
        if value["requestHash"] != request_hash or type(value["replayed"]) is not bool:
            raise ValueError("content review Receipt identity drifted")
        receipt = cls(
            receipt_ref=exact_ref_from_payload(value["receiptRef"], {"ContentReviewReceipt"}),
            request_hash=request_hash,
            decision=value["decision"],
            artifact_ref=exact_ref_from_payload(value["artifactRef"], {"ArtifactRevision"}),
            task_ref=exact_ref_from_payload(value["taskRef"], {"Task"}),
            brief_ref=exact_ref_from_payload(value["briefRef"], {"TaskBriefRevision"}),
            review_issue_ref=exact_ref_from_payload(
                value["reviewIssueRef"], {"ReviewIssueRevision"}
            ),
            reviewer_authority_ref=exact_ref_from_payload(
                value["reviewerAuthorityRef"], {"ReviewerAuthorityRevision"}
            ),
            return_stage=value["returnStage"],
            replayed=value["replayed"],
        )
        expected = (
            (receipt.decision, request.decision),
            (receipt.artifact_ref, request.artifact.artifact_ref),
            (receipt.task_ref, request.artifact.task_ref),
            (receipt.brief_ref, request.artifact.brief_ref),
            (receipt.review_issue_ref, request.review_issue_ref),
            (receipt.reviewer_authority_ref, request.reviewer_authority_ref),
            (receipt.return_stage, request.return_stage),
        )
        if any(actual != wanted for actual, wanted in expected):
            raise ValueError("content review Receipt exact lineage drifted")
        return receipt


def review_content_artifact(
    port: GrowthContentReviewPort,
    *,
    dispatch_ref: DispatchRef,
    request: ContentReviewRequest,
) -> ContentReviewReceipt:
    if dispatch_ref.operation_id != CONTENT_REVIEW_OPERATION or dispatch_ref.handler_kind != "extension":
        raise PermissionError("dispatch does not authorize content review")
    command = request.command_payload()
    request_hash = canonical_command_hash(command)
    result = commit_with_dispatch(port, dispatch_ref, {**command, "requestHash": request_hash})
    return ContentReviewReceipt.from_payload(result, request=request, request_hash=request_hash)


__all__ = [
    "CONTENT_REVIEW_OPERATION",
    "ContentReviewReceipt",
    "ContentReviewRequest",
    "ReadableContentArtifact",
    "review_content_artifact",
    "validated_business_text",
]
