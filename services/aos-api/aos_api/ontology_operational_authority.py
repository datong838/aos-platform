"""Tenant-authoritative operational records shared by Wiki, Action and agents."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_compose import active_ecommerce_installation
from aos_api.tenant_scope import TenantScope


HashRef = str
RiskLevel = Literal["low", "medium", "high"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SubjectRef(StrictModel):
    subject_type: Literal["object_type", "object_instance", "action_type", "rule", "platform", "task_type"] = Field(alias="subjectType")
    subject_id: str = Field(alias="subjectId", min_length=1, max_length=512)
    object_ref: dict[str, str] | None = Field(default=None, alias="objectRef")


class KnowledgeSource(StrictModel):
    source_type: Literal["document", "object", "query", "api", "human_review"] = Field(alias="sourceType")
    source_ref: str = Field(alias="sourceRef", min_length=1, max_length=1024)
    revision: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    captured_at: datetime | None = Field(default=None, alias="capturedAt")
    license_boundary: str | None = Field(default=None, alias="licenseBoundary", max_length=256)


class KnowledgePayload(StrictModel):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1, max_length=100_000)
    level: Literal["L1", "L2", "L3", "L4"] = "L1"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    subject: SubjectRef
    sources: list[KnowledgeSource] = Field(min_length=1, max_length=64)
    visibility: Literal["organization_private", "installed_template"]
    knowledge_pack_id: str | None = Field(default=None, alias="knowledgePackId")
    effective_from: datetime | None = Field(default=None, alias="effectiveFrom")
    effective_until: datetime | None = Field(default=None, alias="effectiveUntil")
    review_cycle_days: int | None = Field(default=None, alias="reviewCycleDays", ge=1, le=3650)
    state: Literal["draft", "approved", "revoked"] = "draft"

    @model_validator(mode="after")
    def validate_visibility(self) -> "KnowledgePayload":
        if self.visibility == "installed_template" and not self.knowledge_pack_id:
            raise ValueError("installed template knowledge requires knowledgePackId")
        if self.effective_from and self.effective_until and self.effective_until <= self.effective_from:
            raise ValueError("effectiveUntil must be after effectiveFrom")
        return self


class RetentionPolicyRef(StrictModel):
    policy_id: str = Field(alias="policyId", min_length=1, max_length=256)
    revision: int = Field(ge=1)


class EvidencePayload(StrictModel):
    subject_ref: dict[str, str] = Field(alias="subjectRef")
    conclusion: str = Field(min_length=1, max_length=4096)
    content_hash: str = Field(alias="contentHash", pattern=r"^sha256:[0-9a-f]{64}$")
    source_ref: str | None = Field(default=None, alias="sourceRef", max_length=2048)
    time_window: dict[str, str] | None = Field(default=None, alias="timeWindow")
    masking_policy_revision: str | None = Field(default=None, alias="maskingPolicyRevision", max_length=256)
    retention_policy_ref: RetentionPolicyRef | None = Field(default=None, alias="retentionPolicyRef")
    sensitive: bool = False
    supersedes_revision: int | None = Field(default=None, alias="supersedesRevision", ge=1)
    revokes_revision: int | None = Field(default=None, alias="revokesRevision", ge=1)

    @model_validator(mode="after")
    def require_retention(self) -> "EvidencePayload":
        if self.sensitive and self.retention_policy_ref is None:
            raise ValueError("sensitive evidence requires retention policy")
        if self.supersedes_revision and self.revokes_revision:
            raise ValueError("evidence cannot supersede and revoke in one revision")
        return self


class RetentionPolicyPayload(StrictModel):
    data_category: str = Field(alias="dataCategory", min_length=1, max_length=256)
    duration_days: int = Field(alias="durationDays", ge=1, le=36500)
    cleanup_mode: Literal["delete_content_keep_hash"] = Field(alias="cleanupMode")
    policy_owner: str = Field(alias="policyOwner", min_length=1, max_length=256)


class ActionPolicy(StrictModel):
    risk_level: RiskLevel = Field(alias="riskLevel")
    requires_approval: bool = Field(alias="requiresApproval")
    capabilities: set[str] = Field(default_factory=set, max_length=128)
    disabled: bool = False


class ActionTypePayload(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    input_schema: dict[str, Any] = Field(alias="inputSchema")
    output_schema: dict[str, Any] = Field(alias="outputSchema")
    policy: ActionPolicy
    timeout_seconds: int = Field(alias="timeoutSeconds", ge=1, le=86400)
    compensation_action_type: str | None = Field(default=None, alias="compensationActionType", max_length=256)


class RevisionRef(StrictModel):
    record_id: str = Field(alias="recordId", min_length=1, max_length=512)
    revision: int = Field(ge=1)


class ActionInstancePayload(StrictModel):
    action_type_ref: RevisionRef = Field(alias="actionTypeRef")
    status: Literal["proposed", "approved", "running", "succeeded", "failed", "compensated"]
    risk_level: RiskLevel = Field(alias="riskLevel")
    requires_approval: bool = Field(alias="requiresApproval")
    task_ref: dict[str, Any] | None = Field(default=None, alias="taskRef")
    object_ref: dict[str, str] | None = Field(default=None, alias="objectRef")
    input_snapshot_hash: str = Field(alias="inputSnapshotHash", pattern=r"^sha256:[0-9a-f]{64}$")
    approval_ref: str | None = Field(default=None, alias="approvalRef", max_length=512)
    receipt_ref: str | None = Field(default=None, alias="receiptRef", max_length=512)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list, alias="evidenceRefs", max_length=128)

    @model_validator(mode="after")
    def approval_is_server_enforced(self) -> "ActionInstancePayload":
        if self.requires_approval and self.status not in {"proposed"} and not self.approval_ref:
            raise ValueError("approved side-effect action requires approvalRef")
        return self


class TaskPayload(StrictModel):
    status: Literal["draft", "queued", "running", "blocked", "completed", "failed", "cancelled"]
    risk_level: RiskLevel = Field(alias="riskLevel")
    initiated_by: str = Field(alias="initiatedBy", min_length=1, max_length=256)
    assigned_agent: str | None = Field(default=None, alias="assignedAgent", max_length=256)
    target_object: dict[str, str] | None = Field(default=None, alias="targetObject")
    plan: dict[str, Any]
    checkpoint_refs: list[str] = Field(default_factory=list, alias="checkpointRefs", max_length=512)


class PlanPayload(StrictModel):
    task_ref: dict[str, Any] = Field(alias="taskRef")
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=512)
    rollback_strategy: dict[str, Any] | None = Field(default=None, alias="rollbackStrategy")


class CheckpointPayload(StrictModel):
    task_ref: dict[str, Any] = Field(alias="taskRef")
    plan_ref: dict[str, Any] = Field(alias="planRef")
    step_id: str = Field(alias="stepId", min_length=1, max_length=256)
    status: Literal["reached", "verified", "rolled_back", "failed"]
    snapshot_hash: str = Field(alias="snapshotHash", pattern=r"^sha256:[0-9a-f]{64}$")
    reflection: dict[str, Any] | None = None


class ArtifactPayload(StrictModel):
    task_ref: dict[str, Any] = Field(alias="taskRef")
    step_id: str = Field(alias="stepId", min_length=1, max_length=256)
    storage_ref: str = Field(alias="storageRef", min_length=1, max_length=2048)
    content_hash: str = Field(alias="contentHash", pattern=r"^sha256:[0-9a-f]{64}$")
    input_snapshot_hash: str = Field(alias="inputSnapshotHash", pattern=r"^sha256:[0-9a-f]{64}$")


class EvalPayload(StrictModel):
    task_ref: dict[str, Any] = Field(alias="taskRef")
    target_ref: dict[str, Any] = Field(alias="targetRef")
    metric_results: dict[str, Any] = Field(alias="metricResults")
    passed: bool
    evidence_refs: list[dict[str, Any]] = Field(alias="evidenceRefs", min_length=1, max_length=128)


_MODELS: dict[str, type[StrictModel]] = {
    "knowledge": KnowledgePayload,
    "action_type": ActionTypePayload,
    "action_instance": ActionInstancePayload,
    "task": TaskPayload,
    "plan": PlanPayload,
    "checkpoint": CheckpointPayload,
    "artifact": ArtifactPayload,
    "eval": EvalPayload,
    "evidence": EvidencePayload,
    "retention_policy": RetentionPolicyPayload,
}


def validate_payload(record_kind: str, payload: dict[str, Any]) -> StrictModel:
    model = _MODELS.get(record_kind)
    if model is None:
        raise ValueError("unknown operational record kind")
    return model.model_validate(payload)


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compose_action_policy(base: ActionPolicy, overlay: ActionPolicy) -> ActionPolicy:
    rank = {"low": 0, "medium": 1, "high": 2}
    if rank[overlay.risk_level] < rank[base.risk_level]:
        raise ValueError("organization overlay cannot lower action risk")
    if base.requires_approval and not overlay.requires_approval:
        raise ValueError("organization overlay cannot remove approval")
    if not overlay.capabilities.issubset(base.capabilities):
        raise ValueError("organization overlay capabilities must be a subset")
    if base.disabled and not overlay.disabled:
        raise ValueError("organization overlay cannot enable a disabled action")
    return overlay


def composed_policy_etag(base: ActionPolicy, overlay: ActionPolicy) -> str:
    composed = compose_action_policy(base, overlay)
    return "action-policy-v1:sha256:" + canonical_hash({
        "base": base.model_dump(mode="json", by_alias=True),
        "overlay": composed.model_dump(mode="json", by_alias=True),
    })


def _tables(record_kind: str) -> tuple[str, str]:
    if record_kind not in _MODELS:
        raise ValueError("unknown operational record kind")
    return f"ontology_{record_kind}_head", f"ontology_{record_kind}_revision"


def append_record(
    scope: TenantScope,
    *,
    record_kind: str,
    record_id: str,
    payload: dict[str, Any],
    expected_revision: int,
    idempotency_key: str,
    actor: str,
) -> tuple[dict[str, Any], str]:
    if expected_revision < 0 or not record_id.strip() or not idempotency_key.strip() or not actor.strip():
        raise ValueError("record id, revision, idempotency key and actor are required")
    normalized = validate_payload(record_kind, payload).model_dump(mode="json", by_alias=True)
    request_hash = canonical_hash({
        "scope": scope.key, "recordKind": record_kind, "recordId": record_id,
        "expectedRevision": expected_revision, "payload": normalized,
    })
    head_table, revision_table = _tables(record_kind)
    with connect(scope) as conn:
        receipt = conn.execute(
            "SELECT request_hash,response_etag,result_json FROM ontology_authority_receipt "
            "WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s",
            (*scope.key, idempotency_key),
        ).fetchone()
        if receipt is not None:
            if receipt["request_hash"] != request_hash:
                raise ApiError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload differs", status_code=409)
            return dict(receipt["result_json"]), receipt["response_etag"]
        conn.execute(
            f"INSERT INTO {head_table}(org_id,workspace_id,record_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (*scope.key, record_id),
        )
        head = conn.execute(
            f"SELECT active_revision,archived_at FROM {head_table} WHERE org_id=%s AND workspace_id=%s AND record_id=%s FOR UPDATE",
            (*scope.key, record_id),
        ).fetchone()
        current = int(head["active_revision"])
        if head["archived_at"] is not None:
            raise ApiError(code="OPERATIONAL_RECORD_ARCHIVED", message="record is archived", status_code=409)
        if current != expected_revision:
            raise ApiError(code="REVISION_CONFLICT", message="operational record revision changed", status_code=412, details={"expected": expected_revision, "actual": current})
        if record_kind == "evidence":
            evidence = EvidencePayload.model_validate(normalized)
            if evidence.retention_policy_ref is not None:
                policy = conn.execute(
                    "SELECT 1 FROM ontology_retention_policy_revision WHERE org_id=%s AND workspace_id=%s "
                    "AND record_id=%s AND revision=%s",
                    (*scope.key, evidence.retention_policy_ref.policy_id, evidence.retention_policy_ref.revision),
                ).fetchone()
                if policy is None:
                    raise ApiError(code="RETENTION_POLICY_NOT_FOUND", message="retention policy revision not found", status_code=409)
            correction_revision = evidence.supersedes_revision or evidence.revokes_revision
            if correction_revision is not None:
                referenced = conn.execute(
                    "SELECT 1 FROM ontology_evidence_revision WHERE org_id=%s AND workspace_id=%s "
                    "AND record_id=%s AND revision=%s",
                    (*scope.key, record_id, correction_revision),
                ).fetchone()
                if referenced is None:
                    raise ApiError(
                        code="EVIDENCE_REVISION_NOT_FOUND",
                        message="superseded or revoked evidence revision not found",
                        status_code=409,
                    )
        if record_kind == "action_instance":
            instance = ActionInstancePayload.model_validate(normalized)
            action_type_row = conn.execute(
                "SELECT payload FROM ontology_action_type_revision WHERE org_id=%s AND workspace_id=%s "
                "AND record_id=%s AND revision=%s",
                (*scope.key, instance.action_type_ref.record_id, instance.action_type_ref.revision),
            ).fetchone()
            if action_type_row is None:
                raise ApiError(code="ACTION_TYPE_NOT_FOUND", message="action type revision not found", status_code=409)
            action_type = ActionTypePayload.model_validate(action_type_row["payload"])
            if instance.risk_level != action_type.policy.risk_level:
                raise ApiError(
                    code="ACTION_POLICY_MISMATCH",
                    message="action instance risk must equal the authoritative action type policy",
                    status_code=409,
                )
            if instance.requires_approval != action_type.policy.requires_approval:
                raise ApiError(
                    code="ACTION_POLICY_MISMATCH",
                    message="action instance approval must equal the authoritative action type policy",
                    status_code=409,
                )
        revision = current + 1
        payload_hash = canonical_hash(normalized)
        supersedes = normalized.get("supersedesRevision")
        revokes = normalized.get("revokesRevision")
        conn.execute(
            f"INSERT INTO {revision_table}(org_id,workspace_id,record_id,revision,payload,payload_hash,"
            "supersedes_revision,revokes_revision,created_by) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
            (*scope.key, record_id, revision, json.dumps(normalized, ensure_ascii=False), payload_hash, supersedes, revokes, actor),
        )
        conn.execute(
            f"UPDATE {head_table} SET active_revision=%s,updated_at=now() WHERE org_id=%s AND workspace_id=%s AND record_id=%s",
            (revision, *scope.key, record_id),
        )
        etag = f'"ontology-{record_kind}-v1:{revision}:{payload_hash}"'
        result = {"recordKind": record_kind, "recordId": record_id, "revision": revision, "payload": normalized, "payloadHash": payload_hash}
        conn.execute(
            "INSERT INTO ontology_authority_receipt(org_id,workspace_id,idempotency_key,request_hash,"
            "record_kind,record_id,expected_revision,resulting_revision,response_etag,result_json,actor) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (*scope.key, idempotency_key, request_hash, record_kind, record_id, expected_revision, revision, etag, json.dumps(result, ensure_ascii=False), actor),
        )
        return result, etag


def read_record(scope: TenantScope, *, record_kind: str, record_id: str) -> dict[str, Any] | None:
    head_table, revision_table = _tables(record_kind)
    with connect(scope) as conn:
        row = conn.execute(
            f"SELECT r.* FROM {head_table} h JOIN {revision_table} r ON r.org_id=h.org_id "
            "AND r.workspace_id=h.workspace_id AND r.record_id=h.record_id AND r.revision=h.active_revision "
            "WHERE h.org_id=%s AND h.workspace_id=%s AND h.record_id=%s AND h.archived_at IS NULL",
            (*scope.key, record_id),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row["payload"])
        if record_kind == "knowledge" and payload.get("visibility") == "installed_template":
            if active_ecommerce_installation(conn, scope) is None:
                return None
        return {"recordKind": record_kind, "recordId": record_id, "revision": row["revision"], "payload": payload, "payloadHash": row["payload_hash"]}


def archive_record(
    scope: TenantScope,
    *,
    record_kind: str,
    record_id: str,
    expected_revision: int,
    idempotency_key: str,
    actor: str,
) -> dict[str, Any]:
    if expected_revision < 1 or not record_id.strip() or not idempotency_key.strip() or not actor.strip():
        raise ValueError("record id, active revision, idempotency key and actor are required")
    head_table, _ = _tables(record_kind)
    request_hash = canonical_hash({
        "scope": scope.key,
        "operation": "archive",
        "recordKind": record_kind,
        "recordId": record_id,
        "expectedRevision": expected_revision,
    })
    with connect(scope) as conn:
        receipt = conn.execute(
            "SELECT request_hash,result_json FROM ontology_authority_archive_receipt "
            "WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s",
            (*scope.key, idempotency_key),
        ).fetchone()
        if receipt is not None:
            if receipt["request_hash"] != request_hash:
                raise ApiError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload differs", status_code=409)
            return dict(receipt["result_json"])
        head = conn.execute(
            f"SELECT active_revision,archived_at FROM {head_table} WHERE org_id=%s AND workspace_id=%s "
            "AND record_id=%s FOR UPDATE",
            (*scope.key, record_id),
        ).fetchone()
        if head is None:
            raise ApiError(code="OPERATIONAL_RECORD_NOT_FOUND", message="record not found", status_code=404)
        if int(head["active_revision"]) != expected_revision:
            raise ApiError(code="REVISION_CONFLICT", message="operational record revision changed", status_code=412)
        if head["archived_at"] is None:
            conn.execute(
                f"UPDATE {head_table} SET archived_at=now(),updated_at=now() "
                "WHERE org_id=%s AND workspace_id=%s AND record_id=%s",
                (*scope.key, record_id),
            )
        result = {
            "recordKind": record_kind,
            "recordId": record_id,
            "revision": expected_revision,
            "archived": True,
        }
        conn.execute(
            "INSERT INTO ontology_authority_archive_receipt(org_id,workspace_id,idempotency_key,request_hash," 
            "record_kind,record_id,expected_revision,result_json,actor) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (*scope.key, idempotency_key, request_hash, record_kind, record_id, expected_revision,
             json.dumps(result, ensure_ascii=False), actor),
        )
        return result


def record_evidence_cleanup(
    scope: TenantScope,
    *,
    evidence_id: str,
    evidence_revision: int,
    idempotency_key: str,
    actor: str,
) -> dict[str, Any]:
    if evidence_revision < 1 or not evidence_id.strip() or not idempotency_key.strip() or not actor.strip():
        raise ValueError("evidence id, revision, idempotency key and actor are required")
    request_hash = canonical_hash({
        "scope": scope.key,
        "evidenceId": evidence_id,
        "evidenceRevision": evidence_revision,
    })
    with connect(scope) as conn:
        existing = conn.execute(
            "SELECT request_hash,cleanup_id,evidence_id,evidence_revision,content_hash,policy_id,policy_revision," 
            "actor,cleaned_at FROM ontology_evidence_cleanup_receipt "
            "WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s",
            (*scope.key, idempotency_key),
        ).fetchone()
        if existing is not None:
            if existing["request_hash"] != request_hash:
                raise ApiError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload differs", status_code=409)
            return _cleanup_result(existing)
        evidence_row = conn.execute(
            "SELECT payload FROM ontology_evidence_revision WHERE org_id=%s AND workspace_id=%s "
            "AND record_id=%s AND revision=%s",
            (*scope.key, evidence_id, evidence_revision),
        ).fetchone()
        if evidence_row is None:
            raise ApiError(code="EVIDENCE_REVISION_NOT_FOUND", message="evidence revision not found", status_code=404)
        evidence = EvidencePayload.model_validate(evidence_row["payload"])
        if evidence.retention_policy_ref is None:
            raise ApiError(code="RETENTION_POLICY_REQUIRED", message="evidence has no retention policy", status_code=409)
        row = conn.execute(
            "INSERT INTO ontology_evidence_cleanup_receipt(org_id,workspace_id,idempotency_key,request_hash," 
            "evidence_id,evidence_revision,content_hash,policy_id,policy_revision,actor) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "RETURNING cleanup_id,evidence_id,evidence_revision,content_hash,policy_id,policy_revision,actor,cleaned_at,request_hash",
            (*scope.key, idempotency_key, request_hash, evidence_id, evidence_revision,
             evidence.content_hash.removeprefix("sha256:"), evidence.retention_policy_ref.policy_id,
             evidence.retention_policy_ref.revision, actor),
        ).fetchone()
        return _cleanup_result(row)


def _cleanup_result(row: dict[str, Any]) -> dict[str, Any]:
    cleanup_id = row["cleanup_id"]
    return {
        "cleanupId": str(cleanup_id if isinstance(cleanup_id, UUID) else cleanup_id),
        "evidenceId": row["evidence_id"],
        "evidenceRevision": int(row["evidence_revision"]),
        "contentHash": "sha256:" + row["content_hash"],
        "policyRef": {"policyId": row["policy_id"], "revision": int(row["policy_revision"])},
        "actor": row["actor"],
        "cleanedAt": row["cleaned_at"].isoformat(),
    }
