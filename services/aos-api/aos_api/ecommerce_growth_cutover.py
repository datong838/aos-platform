"""Trusted host authority for atomic ecommerce growth dispatch cutover."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import psycopg
from pydantic import Field, StrictInt, field_validator, model_validator
from psycopg.types.json import Jsonb

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class EcommerceGrowthCutoverError(RuntimeError):
    code = "ECOMMERCE_GROWTH_CUTOVER_ERROR"


class EcommerceGrowthCutoverConflict(EcommerceGrowthCutoverError):
    code = "ECOMMERCE_GROWTH_CUTOVER_CONFLICT"


class EcommerceGrowthCutoverBlocked(EcommerceGrowthCutoverError):
    code = "ECOMMERCE_GROWTH_CUTOVER_BLOCKED"


class CutoverExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=240)
    revision: StrictInt = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("resource_type", "resource_id")
    @classmethod
    def _canonical_identity(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("cutover exact reference identity must be canonical")
        return value


class CutoverPrepareRequest(AipContractModel):
    cutover_operation_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=240)
    cutover_group_id: UUID
    expected_group_revision: StrictInt = Field(ge=1)
    target_installation_id: UUID
    target_generation: UUID
    target_execution_epoch: StrictInt = Field(ge=1)
    target_runtime_revision: StrictInt = Field(ge=1)
    policy_ref: CutoverExactRef
    approval_ref: CutoverExactRef
    checkpoint: dict[str, Any]
    occurrence_watermark: datetime | None = None
    pending_target_receipt_refs: tuple[CutoverExactRef, ...] = ()
    registration_receipt_ref: RegistrationReceiptRef | None = None

    @field_validator("idempotency_key")
    @classmethod
    def _canonical_key(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("cutover idempotency key must be canonical")
        return value

    @model_validator(mode="after")
    def _authority_shapes(self) -> "CutoverPrepareRequest":
        if self.approval_ref.resource_type != "ActionApprovalEvent":
            raise ValueError("approvalRef must reference ActionApprovalEvent")
        if self.occurrence_watermark is not None and self.occurrence_watermark.tzinfo is None:
            raise ValueError("occurrenceWatermark must include timezone")
        identities = [
            (item.resource_type, item.resource_id, item.revision, item.content_hash)
            for item in self.pending_target_receipt_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("pending target Receipt refs must be unique")
        canonical_sha256(self.checkpoint)
        return self

    def request_hash(self) -> str:
        payload = self.model_dump(mode="json", by_alias=True)
        if self.registration_receipt_ref is None:
            payload.pop("registrationReceiptRef", None)
        return canonical_sha256(payload)


class CutoverPrepareReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: UUID
    cutover_operation_id: UUID
    status: Literal["prepared"] = "prepared"
    cutover_group_id: UUID
    expected_group_revision: int
    target_group_revision: int
    target_installation_id: UUID
    target_generation: UUID
    target_execution_epoch: int
    target_runtime_revision: int
    operation_ids: tuple[str, ...]
    old_dispatch_snapshot: tuple[dict[str, Any], ...]
    new_dispatch_snapshot: tuple[dict[str, Any], ...]
    checkpoint: dict[str, Any]
    occurrence_watermark: datetime | None
    pending_target_receipt_refs: tuple[CutoverExactRef, ...]
    registration_receipt_ref: RegistrationReceiptRef | None = None
    policy_ref: CutoverExactRef
    approval_ref: CutoverExactRef
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replayed: bool = False
    created_at: datetime


class CutoverCommitRequest(AipContractModel):
    cutover_operation_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=240)
    prepare_receipt_ref: CutoverExactRef

    @field_validator("idempotency_key")
    @classmethod
    def _canonical_key(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("cutover commit idempotency key must be canonical")
        return value

    @model_validator(mode="after")
    def _prepare_ref(self) -> "CutoverCommitRequest":
        if self.prepare_receipt_ref.resource_type != "CutoverPrepareReceipt":
            raise ValueError("prepareReceiptRef must reference CutoverPrepareReceipt")
        try:
            UUID(self.prepare_receipt_ref.resource_id)
        except ValueError as exc:
            raise ValueError("prepareReceiptRef resourceId must be a UUID") from exc
        return self

    def request_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", by_alias=True))


class CutoverApprovalRefreshRequest(AipContractModel):
    cutover_operation_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=240)
    prepare_receipt_ref: CutoverExactRef
    approval_ref: CutoverExactRef

    @model_validator(mode="after")
    def _refs(self) -> "CutoverApprovalRefreshRequest":
        if self.idempotency_key != self.idempotency_key.strip():
            raise ValueError("cutover approval refresh key must be canonical")
        if self.prepare_receipt_ref.resource_type != "CutoverPrepareReceipt":
            raise ValueError("prepareReceiptRef must reference CutoverPrepareReceipt")
        if self.approval_ref.resource_type != "ActionApprovalEvent":
            raise ValueError("approvalRef must reference ActionApprovalEvent")
        return self

    def request_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", by_alias=True))


class CutoverApprovalRefreshReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: UUID
    cutover_operation_id: UUID
    status: Literal["approval_refreshed"] = "approval_refreshed"
    prepare_receipt_ref: CutoverExactRef
    old_approval_ref: CutoverExactRef
    new_approval_ref: CutoverExactRef
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replayed: bool = False
    created_at: datetime


class CutoverCommitPhaseReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: UUID
    cutover_operation_id: UUID
    phase: Literal["pause", "commit"]
    status: Literal["draining", "committed"]
    cutover_group_id: UUID
    operation_ids: tuple[str, ...]
    dispatch_snapshot: tuple[dict[str, Any], ...]
    occurrence_watermark: datetime | None
    claimed_occurrences: tuple[dict[str, Any], ...]
    claimed_attempts: tuple[dict[str, Any], ...]
    unknown_attempts: tuple[dict[str, Any], ...]
    running_runtime_attempts: tuple[dict[str, Any], ...]
    pending_target_receipt_refs: tuple[CutoverExactRef, ...]
    prepare_receipt_ref: CutoverExactRef
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    claim_paused: Literal[True] = True
    replayed: bool = False
    created_at: datetime


class CutoverFinalizeRequest(AipContractModel):
    cutover_operation_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=240)
    commit_receipt_ref: CutoverExactRef

    @field_validator("idempotency_key")
    @classmethod
    def _canonical_key(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("cutover finalize idempotency key must be canonical")
        return value

    @model_validator(mode="after")
    def _commit_ref(self) -> "CutoverFinalizeRequest":
        if self.commit_receipt_ref.resource_type != "CutoverCommitReceipt":
            raise ValueError("commitReceiptRef must reference CutoverCommitReceipt")
        try:
            UUID(self.commit_receipt_ref.resource_id)
        except ValueError as exc:
            raise ValueError("commitReceiptRef resourceId must be a UUID") from exc
        return self

    def request_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", by_alias=True))


class CutoverFinalizeReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: UUID
    cutover_operation_id: UUID
    phase: Literal["validate", "resume"]
    status: Literal["validated", "resumed"]
    cutover_group_id: UUID
    operation_ids: tuple[str, ...]
    dispatch_snapshot: tuple[dict[str, Any], ...]
    target_runtime_revision: int
    claim_paused: bool
    occurrence_watermark: datetime | None
    claimed_occurrences: tuple[dict[str, Any], ...]
    claimed_attempts: tuple[dict[str, Any], ...]
    unknown_attempts: tuple[dict[str, Any], ...]
    running_runtime_attempts: tuple[dict[str, Any], ...]
    commit_receipt_ref: CutoverExactRef
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replayed: bool = False
    created_at: datetime


class CutoverRollbackRequest(AipContractModel):
    rollback_operation_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=240)
    activation_operation_id: UUID
    commit_receipt_ref: CutoverExactRef
    approval_ref: CutoverExactRef
    failure_reason: str = Field(min_length=1, max_length=1000)

    @field_validator("idempotency_key", "failure_reason")
    @classmethod
    def _canonical_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("rollback text must be canonical")
        return value

    @model_validator(mode="after")
    def _refs(self) -> "CutoverRollbackRequest":
        if self.commit_receipt_ref.resource_type != "CutoverCommitReceipt":
            raise ValueError("commitReceiptRef must reference CutoverCommitReceipt")
        if self.approval_ref.resource_type != "ActionApprovalEvent":
            raise ValueError("approvalRef must reference ActionApprovalEvent")
        return self

    def request_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", by_alias=True))


class CutoverRollbackReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: UUID
    rollback_operation_id: UUID
    activation_operation_id: UUID
    phase: Literal["fence", "drain", "rollback"]
    status: Literal["draining", "rolled_back"]
    cutover_group_id: UUID
    operation_ids: tuple[str, ...]
    dispatch_snapshot: tuple[dict[str, Any], ...]
    occurrence_watermark: datetime | None
    claimed_occurrences: tuple[dict[str, Any], ...]
    claimed_attempts: tuple[dict[str, Any], ...]
    unknown_attempts: tuple[dict[str, Any], ...]
    running_runtime_attempts: tuple[dict[str, Any], ...]
    commit_receipt_ref: CutoverExactRef
    approval_ref: CutoverExactRef
    failure_reason: str
    drain_receipt_ref: CutoverExactRef | None = None
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replayed: bool = False
    created_at: datetime


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if type(value) is not dict:
        raise EcommerceGrowthCutoverConflict("stored cutover authority is malformed")
    return value


def _array(value: Any) -> list[Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if type(value) is not list:
        raise EcommerceGrowthCutoverConflict("stored cutover authority is malformed")
    return value


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "operationId": str(row["operation_id"]),
        "handlerKind": str(row["handler_kind"]),
        "installationId": None if row["installation_id"] is None else str(row["installation_id"]),
        "generation": None if row["generation"] is None else str(row["generation"]),
        "executionEpoch": row["execution_epoch"],
        "operationFence": row["operation_fence"],
        "revision": int(row["revision"]),
        "cutoverGroupId": str(row["cutover_group_id"]),
        "cutoverGroupRevision": int(row["cutover_group_revision"]),
    }


class EcommerceGrowthCutoverStore:
    """Prepare exact group snapshots without changing the active dispatch pointer."""

    def __init__(self, connect_factory: ConnectFactory, *, schema: str = "public", registration_service=None) -> None:
        if not callable(connect_factory):
            raise TypeError("dedicated cutover maintainer connection is required")
        if re.fullmatch(r"[a-z_][a-z0-9_]*", schema) is None:
            raise ValueError("cutover schema is invalid")
        self._connect_factory = connect_factory
        self._schema = schema
        from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
        if registration_service is not None and type(registration_service) is not FirstDispatchRegistrationService:
            raise TypeError("production registration service required")
        self._registration_service = registration_service

    def read_prepare_receipt(
        self, *, scope: TenantScope, installation_id: str, idempotency_key: str, actor: str,
    ) -> dict[str, Any]:
        """Read historical evidence by its original key; never replay a write."""
        with self._prepare_read_context(scope, installation_id, idempotency_key, actor) as (_, _, receipt):
            return {"receipt": receipt.model_dump(mode="json", by_alias=True),
                    "historical": True, "executable": False}

    def read_activation_history(self, *, scope: TenantScope, installation_id: str,
                                idempotency_key: str, actor: str) -> dict[str, Any]:
        from aos_api.ecommerce_growth_cutover_history import activation_history
        with self._prepare_read_context(scope, installation_id, idempotency_key, actor) as (conn, row, receipt):
            return activation_history(self, conn, scope, row, receipt)

    @contextmanager
    def _prepare_read_context(self, scope, installation_id, idempotency_key, actor):
        from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
        FirstDispatchRegistrationService._identity(scope, actor)
        if (type(installation_id) is not str or str(UUID(installation_id)) != installation_id
                or type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 240
                or idempotency_key != idempotency_key.strip() or not idempotency_key.isprintable()):
            raise ValueError("canonical cutover receipt identity required")
        if self._registration_service is None:
            raise EcommerceGrowthCutoverBlocked("current receipt authorization is not wired")
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            conn.execute("SET LOCAL ROLE aos_runtime")
            self._registration_service._authorize_receipt_access(conn, scope, installation_id, actor)
            conn.execute("SET LOCAL ROLE aos_extension_maintainer")
            row = conn.execute(
                f"""SELECT o.*,r.receipt_id,r.request_hash AS receipt_request_hash,
                            r.authority_data,r.content_hash,r.created_at AS receipt_created_at
                     FROM {self._schema}.extension_dispatch_cutover_operation o
                     JOIN {self._schema}.extension_dispatch_cutover_receipt r
                       USING(org_id,project_id,cutover_operation_id)
                    WHERE o.org_id=%s AND o.project_id=%s AND o.target_installation_id=%s
                      AND o.idempotency_key=%s AND o.kind='activate' AND r.phase='prepare'""",
                (*scope.key, installation_id, idempotency_key),
            ).fetchone()
            if row is None:
                raise LookupError("cutover prepare receipt unavailable")
            receipt = self._receipt(scope, row, replayed=True)
            yield conn, row, receipt

    def prepare_activation(
        self,
        scope: TenantScope,
        request: CutoverPrepareRequest,
        *,
        actor: str,
    ) -> CutoverPrepareReceipt:
        if type(scope) is not TenantScope or type(request) is not CutoverPrepareRequest:
            raise TypeError("trusted TenantScope and CutoverPrepareRequest are required")
        request = CutoverPrepareRequest.model_validate(
            request.model_dump(mode="python", by_alias=True)
        )
        if type(actor) is not str or not actor or actor != actor.strip() or len(actor) > 240:
            raise ValueError("canonical cutover actor is required")
        if request.registration_receipt_ref is not None and self._registration_service is None:
            raise EcommerceGrowthCutoverBlocked("first registration activation is not wired")
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            existing = conn.execute(
                f"""SELECT o.*,r.receipt_id,r.request_hash AS receipt_request_hash,
                            r.authority_data,r.content_hash,r.created_at AS receipt_created_at
                     FROM {self._schema}.extension_dispatch_cutover_operation o
                     JOIN {self._schema}.extension_dispatch_cutover_receipt r USING(org_id,project_id,cutover_operation_id)
                    WHERE o.org_id=%s AND o.project_id=%s AND o.idempotency_key=%s
                      AND r.phase='prepare' FOR SHARE OF o""",
                (*scope.key, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["request_hash"] != request_hash
                    or UUID(str(existing["cutover_operation_id"])) != request.cutover_operation_id
                ):
                    raise EcommerceGrowthCutoverConflict("cutover prepare idempotency payload drifted")
                return self._receipt(scope, existing, replayed=True)

            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{scope.org_id}\x1f{scope.project_id}\x1f{request.cutover_group_id}",),
            )
            rows = conn.execute(
                f"""SELECT operation_id,handler_kind,installation_id,generation,execution_epoch,
                          operation_fence,revision,cutover_group_id,cutover_group_revision
                     FROM {self._schema}.extension_operation_dispatch_binding
                    WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
                    ORDER BY operation_id""",
                (*scope.key, request.cutover_group_id),
            ).fetchall()
            expected_operations = tuple(sorted(ECOMMERCE_GROWTH_OPERATIONS))
            if tuple(str(row["operation_id"]) for row in rows) != expected_operations:
                raise EcommerceGrowthCutoverBlocked("cutover group must contain the exact nine operations")
            if any(
                row["handler_kind"] != "legacy"
                or row["operation_fence"] is not (request.registration_receipt_ref is not None)
                or (request.registration_receipt_ref is not None
                    and request.registration_receipt_ref.resourceType == "FirstDispatchRegistrationReceipt"
                    and row["revision"] != 1)
                or int(row["cutover_group_revision"]) != request.expected_group_revision
                for row in rows
            ):
                raise EcommerceGrowthCutoverConflict("legacy dispatch group authority drifted")

            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{scope.org_id}\x1f{scope.project_id}\x1f{request.target_installation_id}",),
            )
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{scope.org_id}\x1f{scope.project_id}\x1f{request.target_installation_id}"
                 f"\x1f{request.target_generation}",),
            )
            runtime = conn.execute(
                f"""SELECT installation_id,generation,execution_epoch,desired_state,observed_state,
                          enabled,operation_fence,revision
                     FROM {self._schema}.extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                    """,
                (*scope.key, request.target_installation_id, request.target_generation),
            ).fetchone()
            if runtime is None:
                raise EcommerceGrowthCutoverBlocked("target runtime binding is unavailable")
            if (
                int(runtime["execution_epoch"]) != request.target_execution_epoch
                or int(runtime["revision"]) != request.target_runtime_revision
                or runtime["desired_state"] != "enabled"
                or runtime["observed_state"] != "ready"
                or runtime["enabled"] is not True
                or runtime["operation_fence"] is not False
            ):
                raise EcommerceGrowthCutoverConflict("target runtime binding is not exact and ready")

            self._registration_assets(conn,scope,request,[_snapshot(dict(row)) for row in rows],actor)
            conn.execute(
                f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
                (request.approval_ref.resource_id,),
            )
            checked_at = self._approval_authority(conn, scope, request)
            old_snapshot = [_snapshot(dict(row)) for row in rows]
            new_snapshot = [
                {
                    **item,
                    "handlerKind": "extension",
                    "installationId": str(request.target_installation_id),
                    "generation": str(request.target_generation),
                    "executionEpoch": request.target_execution_epoch,
                    "operationFence": False,
                    "revision": item["revision"] + 1,
                    "cutoverGroupRevision": request.expected_group_revision + 1,
                }
                for item in old_snapshot
            ]
            pending_refs = [
                item.model_dump(mode="json", by_alias=True)
                for item in request.pending_target_receipt_refs
            ]
            policy_ref = request.policy_ref.model_dump(mode="json", by_alias=True)
            approval_ref = request.approval_ref.model_dump(mode="json", by_alias=True)
            authority = {
                "schemaVersion": "aos.ecommerce.dispatch-cutover-prepare/v1",
                "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                "cutoverOperationId": str(request.cutover_operation_id),
                "status": "prepared",
                "cutoverGroupId": str(request.cutover_group_id),
                "expectedGroupRevision": request.expected_group_revision,
                "targetGroupRevision": request.expected_group_revision + 1,
                "targetInstallationId": str(request.target_installation_id),
                "targetGeneration": str(request.target_generation),
                "targetExecutionEpoch": request.target_execution_epoch,
                "targetRuntimeRevision": request.target_runtime_revision,
                "operationIds": list(expected_operations),
                "oldDispatchSnapshot": old_snapshot,
                "newDispatchSnapshot": new_snapshot,
                "checkpoint": request.checkpoint,
                "occurrenceWatermark": (
                    request.occurrence_watermark.isoformat()
                    if request.occurrence_watermark is not None else None
                ),
                "pendingTargetReceiptRefs": pending_refs,
                "policyRef": policy_ref,
                "approvalRef": approval_ref,
                "requestHash": request_hash,
                "requestedBy": actor,
                "createdAt": checked_at.isoformat(),
            }
            if request.registration_receipt_ref is not None:
                authority["registrationReceiptRef"] = request.registration_receipt_ref.model_dump(mode="json")
            content_hash = canonical_sha256(authority)
            receipt_id, event_id = uuid4(), uuid4()
            conn.execute(
                f"""INSERT INTO {self._schema}.extension_dispatch_cutover_operation(
                     org_id,project_id,cutover_operation_id,kind,idempotency_key,request_hash,status,
                     cutover_group_id,expected_group_revision,target_group_revision,
                     target_installation_id,target_generation,target_execution_epoch,target_runtime_revision,
                     operation_ids,old_dispatch_snapshot,new_dispatch_snapshot,checkpoint,
                     occurrence_watermark,pending_target_receipt_refs,policy_ref,approval_ref,
                     requested_by,created_at,updated_at)
                   VALUES(%s,%s,%s,'activate',%s,%s,'prepared',%s,%s,%s,%s,%s,%s,%s,
                     %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    *scope.key, request.cutover_operation_id, request.idempotency_key, request_hash,
                    request.cutover_group_id, request.expected_group_revision,
                    request.expected_group_revision + 1, request.target_installation_id,
                    request.target_generation, request.target_execution_epoch,
                    request.target_runtime_revision, Jsonb(list(expected_operations)),
                    Jsonb(old_snapshot), Jsonb(new_snapshot), Jsonb(request.checkpoint),
                    request.occurrence_watermark, Jsonb(pending_refs), Jsonb(policy_ref),
                    Jsonb(approval_ref), actor, checked_at, checked_at,
                ),
            )
            event_payload = {
                "cutoverOperationId": str(request.cutover_operation_id),
                "cutoverGroupId": str(request.cutover_group_id),
                "expectedGroupRevision": request.expected_group_revision,
                "targetGroupRevision": request.expected_group_revision + 1,
                "receiptId": str(receipt_id),
                "contentHash": content_hash,
            }
            conn.execute(
                f"""INSERT INTO {self._schema}.extension_dispatch_cutover_event(
                     org_id,project_id,cutover_operation_id,sequence,event_id,event_type,
                     payload,payload_hash,occurred_at)
                   VALUES(%s,%s,%s,1,%s,'CUTOVER_PREPARED',%s,%s,%s)""",
                (*scope.key, request.cutover_operation_id, event_id, Jsonb(event_payload),
                 canonical_sha256(event_payload), checked_at),
            )
            conn.execute(
                f"""INSERT INTO {self._schema}.extension_dispatch_cutover_receipt(
                     org_id,project_id,receipt_id,cutover_operation_id,phase,request_hash,
                     authority_data,content_hash,created_at)
                   VALUES(%s,%s,%s,%s,'prepare',%s,%s,%s,%s)""",
                (*scope.key, receipt_id, request.cutover_operation_id, request_hash,
                 Jsonb(authority), content_hash, checked_at),
            )
            row = conn.execute(
                f"""SELECT o.*,r.receipt_id,r.request_hash AS receipt_request_hash,r.authority_data,r.content_hash,
                            r.created_at AS receipt_created_at
                       FROM {self._schema}.extension_dispatch_cutover_operation o
                       JOIN {self._schema}.extension_dispatch_cutover_receipt r
                         USING(org_id,project_id,cutover_operation_id)
                      WHERE o.org_id=%s AND o.project_id=%s AND o.cutover_operation_id=%s
                        AND r.phase='prepare'""",
                (*scope.key, request.cutover_operation_id),
            ).fetchone()
            if row is None:
                raise EcommerceGrowthCutoverConflict("cutover prepare readback is missing")
            result = self._receipt(scope, row, replayed=False)
            conn.commit()
            return result

    def refresh_activation_approval(
        self,
        scope: TenantScope,
        request: CutoverApprovalRefreshRequest,
        *,
        actor: str,
    ) -> CutoverApprovalRefreshReceipt:
        if type(scope) is not TenantScope or type(request) is not CutoverApprovalRefreshRequest:
            raise TypeError("trusted TenantScope and CutoverApprovalRefreshRequest are required")
        request = CutoverApprovalRefreshRequest.model_validate(
            request.model_dump(mode="python", by_alias=True)
        )
        if type(actor) is not str or not actor or actor != actor.strip() or len(actor) > 240:
            raise ValueError("canonical cutover actor is required")
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            existing = conn.execute(
                f"""SELECT * FROM {self._schema}.extension_dispatch_cutover_approval_refresh_receipt
                      WHERE org_id=%s AND project_id=%s
                        AND (cutover_operation_id=%s OR idempotency_key=%s)""",
                (*scope.key, request.cutover_operation_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if (existing["request_hash"] != request_hash
                        or existing["cutover_operation_id"] != request.cutover_operation_id):
                    raise EcommerceGrowthCutoverConflict("cutover approval refresh idempotency drifted")
                return self._approval_refresh_receipt(scope, dict(existing), replayed=True)
            operation = self._load_operation_with_prepare(conn, scope, request.cutover_operation_id)
            prepare = self._validate_prepare_ref(
                scope, operation, CutoverCommitRequest(
                    cutoverOperationId=request.cutover_operation_id,
                    idempotencyKey=request.idempotency_key,
                    prepareReceiptRef=request.prepare_receipt_ref,
                ),
            )
            if operation["status"] not in {"prepared", "draining"}:
                raise EcommerceGrowthCutoverBlocked("cutover approval can only refresh before commit")
            if request.approval_ref == prepare.approval_ref:
                raise EcommerceGrowthCutoverBlocked("a new current cutover approval is required")
            reconstructed = CutoverPrepareRequest(
                cutoverOperationId=prepare.cutover_operation_id,
                idempotencyKey=operation["idempotency_key"],
                cutoverGroupId=prepare.cutover_group_id,
                expectedGroupRevision=prepare.expected_group_revision,
                targetInstallationId=prepare.target_installation_id,
                targetGeneration=prepare.target_generation,
                targetExecutionEpoch=prepare.target_execution_epoch,
                targetRuntimeRevision=prepare.target_runtime_revision,
                policyRef=prepare.policy_ref,
                approvalRef=request.approval_ref,
                checkpoint=prepare.checkpoint,
                occurrenceWatermark=prepare.occurrence_watermark,
                pendingTargetReceiptRefs=prepare.pending_target_receipt_refs,
                registrationReceiptRef=prepare.registration_receipt_ref,
            )
            conn.execute(
                f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
                (request.approval_ref.resource_id,),
            )
            checked_at = self._approval_authority(conn, scope, reconstructed)
            old_ref = prepare.approval_ref.model_dump(mode="json", by_alias=True)
            new_ref = request.approval_ref.model_dump(mode="json", by_alias=True)
            prepare_ref = request.prepare_receipt_ref.model_dump(mode="json", by_alias=True)
            receipt_id = uuid4()
            authority = {
                "schemaVersion": "aos.ecommerce.dispatch-cutover-approval-refresh/v1",
                "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                "receiptId": str(receipt_id),
                "cutoverOperationId": str(request.cutover_operation_id),
                "status": "approval_refreshed",
                "prepareReceiptRef": prepare_ref,
                "oldApprovalRef": old_ref,
                "newApprovalRef": new_ref,
                "requestHash": request_hash,
                "refreshedBy": actor,
                "createdAt": checked_at.isoformat(),
            }
            content_hash = canonical_sha256(authority)
            conn.execute(
                f"""INSERT INTO {self._schema}.extension_dispatch_cutover_approval_refresh_receipt(
                     org_id,project_id,receipt_id,cutover_operation_id,idempotency_key,request_hash,
                     prepare_receipt_ref,old_approval_ref,new_approval_ref,authority_data,content_hash,
                     refreshed_by,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, receipt_id, request.cutover_operation_id, request.idempotency_key,
                 request_hash, Jsonb(prepare_ref), Jsonb(old_ref), Jsonb(new_ref), Jsonb(authority),
                 content_hash, actor, checked_at),
            )
            row = conn.execute(
                f"""SELECT * FROM {self._schema}.extension_dispatch_cutover_approval_refresh_receipt
                      WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            result = self._approval_refresh_receipt(scope, dict(row), replayed=False)
            conn.commit()
            return result

    def begin_activation_commit(
        self,
        scope: TenantScope,
        request: CutoverCommitRequest,
        *,
        actor: str,
    ) -> CutoverCommitPhaseReceipt:
        scope, request, actor = self._validated_commit_call(scope, request, actor)
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            operation = self._load_operation_with_prepare(conn, scope, request.cutover_operation_id)
            prepare = self._validate_prepare_ref(scope, operation, request)
            existing = self._load_phase_receipt(conn, scope, request.cutover_operation_id, "pause")
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EcommerceGrowthCutoverConflict("cutover pause idempotency payload drifted")
                return self._phase_receipt(scope, existing, replayed=True)
            self._lock_current_prepare_authority(conn, scope, operation, prepare, actor=actor)
            try:
                paused_at = conn.execute(
                    f"SELECT {self._schema}.extension_dispatch_cutover_pause_claims_ar2_014(%s,%s) AS paused_at",
                    (request.cutover_operation_id, actor),
                ).fetchone()["paused_at"]
            except psycopg.Error as exc:
                raise EcommerceGrowthCutoverBlocked(str(exc).splitlines()[0]) from exc
            facts = self._execution_facts(conn, scope, prepare)
            authority = self._phase_authority(
                scope,
                request,
                prepare,
                phase="pause",
                status="draining",
                dispatch_snapshot=list(prepare.old_dispatch_snapshot),
                facts=facts,
                actor=actor,
                created_at=paused_at,
            )
            receipt_id = uuid4()
            self._insert_phase_history(
                conn,
                scope,
                request.cutover_operation_id,
                sequence=2,
                event_type="CUTOVER_CLAIMS_PAUSED",
                phase="pause",
                receipt_id=receipt_id,
                request_hash=request_hash,
                authority=authority,
                occurred_at=paused_at,
            )
            row = self._load_phase_receipt(conn, scope, request.cutover_operation_id, "pause")
            if row is None:
                raise EcommerceGrowthCutoverConflict("cutover pause readback is missing")
            result = self._phase_receipt(scope, row, replayed=False)
            conn.commit()
            return result

    def commit_activation(
        self,
        scope: TenantScope,
        request: CutoverCommitRequest,
        *,
        actor: str,
    ) -> CutoverCommitPhaseReceipt:
        scope, request, actor = self._validated_commit_call(scope, request, actor)
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            operation = self._load_operation_with_prepare(conn, scope, request.cutover_operation_id)
            prepare = self._validate_prepare_ref(scope, operation, request)
            existing = self._load_phase_receipt(conn, scope, request.cutover_operation_id, "commit")
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EcommerceGrowthCutoverConflict("cutover commit idempotency payload drifted")
                return self._phase_receipt(scope, existing, replayed=True)
            pause = self._load_phase_receipt(conn, scope, request.cutover_operation_id, "pause")
            if pause is None or pause["request_hash"] != request_hash:
                raise EcommerceGrowthCutoverBlocked("cutover claims must be paused by this exact request")
            self._phase_receipt(scope, pause, replayed=True)
            if operation["status"] != "draining":
                raise EcommerceGrowthCutoverConflict("cutover operation is not draining")
            self._lock_current_prepare_authority(
                conn, scope, operation, prepare, runtime_draining=True, actor=actor
            )
            facts = self._execution_facts(conn, scope, prepare)
            if prepare.pending_target_receipt_refs:
                raise EcommerceGrowthCutoverBlocked("pending target Receipt reconciliation remains")
            if (
                facts["claimedOccurrences"]
                or facts["claimedAttempts"]
                or facts["runningRuntimeAttempts"]
            ):
                raise EcommerceGrowthCutoverBlocked("cutover target execution is not drained")
            try:
                updated = conn.execute(
                    f"SELECT {self._schema}.extension_dispatch_cutover_commit_ar2_014(%s,%s) AS updated",
                    (request.cutover_operation_id, actor),
                ).fetchone()["updated"]
            except psycopg.Error as exc:
                raise EcommerceGrowthCutoverBlocked(str(exc).splitlines()[0]) from exc
            if int(updated) != len(ECOMMERCE_GROWTH_OPERATIONS):
                raise EcommerceGrowthCutoverConflict("cutover group update was not exact")
            rows = self._dispatch_rows(conn, scope, prepare.cutover_group_id)
            if canonical_hash([_snapshot(dict(row)) for row in rows]) != canonical_hash(
                list(prepare.new_dispatch_snapshot)
            ):
                raise EcommerceGrowthCutoverConflict("committed dispatch readback drifted")
            committed_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            final_facts = self._execution_facts(conn, scope, prepare)
            if (
                final_facts["claimedOccurrences"]
                or final_facts["claimedAttempts"]
                or final_facts["runningRuntimeAttempts"]
            ):
                raise EcommerceGrowthCutoverConflict("execution appeared during cutover commit")
            authority = self._phase_authority(
                scope,
                request,
                prepare,
                phase="commit",
                status="committed",
                dispatch_snapshot=[_snapshot(dict(row)) for row in rows],
                facts=final_facts,
                actor=actor,
                created_at=committed_at,
            )
            receipt_id = uuid4()
            self._insert_phase_history(
                conn,
                scope,
                request.cutover_operation_id,
                sequence=3,
                event_type="CUTOVER_COMMITTED",
                phase="commit",
                receipt_id=receipt_id,
                request_hash=request_hash,
                authority=authority,
                occurred_at=committed_at,
            )
            state = conn.execute(
                f"""SELECT status FROM {self._schema}.extension_dispatch_cutover_operation
                     WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s""",
                (*scope.key, request.cutover_operation_id),
            ).fetchone()
            if state is None or state["status"] != "committed":
                raise EcommerceGrowthCutoverConflict("cutover operation commit state drifted")
            row = self._load_phase_receipt(conn, scope, request.cutover_operation_id, "commit")
            if row is None:
                raise EcommerceGrowthCutoverConflict("cutover commit readback is missing")
            result = self._phase_receipt(scope, row, replayed=False)
            conn.commit()
            return result

    def validate_activation(
        self,
        scope: TenantScope,
        request: CutoverFinalizeRequest,
        *,
        actor: str,
    ) -> CutoverFinalizeReceipt:
        scope, request, actor = self._validated_finalize_call(scope, request, actor)
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            operation, prepare = self._load_committed_context(conn, scope, request)
            existing = self._load_finalize_receipt(
                conn, scope, request.cutover_operation_id, "validate"
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EcommerceGrowthCutoverConflict(
                        "cutover validate idempotency payload drifted"
                    )
                return self._finalize_receipt(scope, existing, replayed=True)
            if operation["status"] != "committed":
                raise EcommerceGrowthCutoverConflict("cutover operation is not committed")
            self._lock_final_authority(conn, scope, operation, prepare, resumed=False, actor=actor)
            facts = self._execution_facts(conn, scope, prepare)
            if prepare.pending_target_receipt_refs:
                raise EcommerceGrowthCutoverBlocked(
                    "pending target Receipt reconciliation remains"
                )
            if (
                facts["claimedOccurrences"]
                or facts["claimedAttempts"]
                or facts["runningRuntimeAttempts"]
            ):
                raise EcommerceGrowthCutoverBlocked("cutover target execution is not drained")
            validated_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            authority = self._finalize_authority(
                scope,
                request,
                prepare,
                phase="validate",
                status="validated",
                runtime_revision=prepare.target_runtime_revision + 1,
                claim_paused=True,
                facts=facts,
                actor=actor,
                created_at=validated_at,
            )
            receipt_id = uuid4()
            self._insert_phase_history(
                conn,
                scope,
                request.cutover_operation_id,
                sequence=4,
                event_type="CUTOVER_VALIDATED",
                phase="validate",
                receipt_id=receipt_id,
                request_hash=request_hash,
                authority=authority,
                occurred_at=validated_at,
            )
            updated = conn.execute(
                f"""UPDATE {self._schema}.extension_dispatch_cutover_operation
                       SET status='validated',updated_at=%s
                     WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s
                       AND status='committed'""",
                (validated_at, *scope.key, request.cutover_operation_id),
            ).rowcount
            if updated != 1:
                raise EcommerceGrowthCutoverConflict("cutover validate state drifted")
            row = self._load_finalize_receipt(
                conn, scope, request.cutover_operation_id, "validate"
            )
            if row is None:
                raise EcommerceGrowthCutoverConflict("cutover validate readback is missing")
            result = self._finalize_receipt(scope, row, replayed=False)
            conn.commit()
            return result

    def resume_activation(
        self,
        scope: TenantScope,
        request: CutoverFinalizeRequest,
        *,
        validate_receipt_ref: CutoverExactRef,
        actor: str,
    ) -> CutoverFinalizeReceipt:
        scope, request, actor = self._validated_finalize_call(scope, request, actor)
        validate_receipt_ref = CutoverExactRef.model_validate(validate_receipt_ref)
        if validate_receipt_ref.resource_type != "CutoverValidateReceipt":
            raise ValueError("validateReceiptRef must reference CutoverValidateReceipt")
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            operation, prepare = self._load_committed_context(conn, scope, request)
            existing = self._load_finalize_receipt(
                conn, scope, request.cutover_operation_id, "resume"
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EcommerceGrowthCutoverConflict(
                        "cutover resume idempotency payload drifted"
                    )
                return self._finalize_receipt(scope, existing, replayed=True)
            validation_row = self._load_finalize_receipt(
                conn, scope, request.cutover_operation_id, "validate"
            )
            if validation_row is None:
                raise EcommerceGrowthCutoverBlocked("exact validate Receipt is required")
            validation = self._finalize_receipt(scope, validation_row, replayed=True)
            if (
                validate_receipt_ref.revision != 1
                or validate_receipt_ref.resource_id != str(validation.receipt_id)
                or validate_receipt_ref.content_hash != validation.content_hash
            ):
                raise EcommerceGrowthCutoverConflict("validate Receipt reference drifted")
            if operation["status"] != "validated":
                raise EcommerceGrowthCutoverConflict("cutover operation is not validated")
            self._lock_final_authority(conn, scope, operation, prepare, resumed=False, actor=actor)
            facts = self._execution_facts(conn, scope, prepare)
            if (
                facts["claimedOccurrences"]
                or facts["claimedAttempts"]
                or facts["runningRuntimeAttempts"]
            ):
                raise EcommerceGrowthCutoverBlocked("cutover target execution is not drained")
            try:
                resumed_at = conn.execute(
                    f"SELECT {self._schema}.extension_dispatch_cutover_resume_ar2_015(%s,%s) AS resumed_at",
                    (request.cutover_operation_id, actor),
                ).fetchone()["resumed_at"]
            except psycopg.Error as exc:
                raise EcommerceGrowthCutoverBlocked(str(exc).splitlines()[0]) from exc
            self._lock_final_authority(conn, scope, operation, prepare, resumed=True, actor=actor)
            final_facts = self._execution_facts(conn, scope, prepare)
            authority = self._finalize_authority(
                scope,
                request,
                prepare,
                phase="resume",
                status="resumed",
                runtime_revision=prepare.target_runtime_revision + 2,
                claim_paused=False,
                facts=final_facts,
                actor=actor,
                created_at=resumed_at,
            )
            receipt_id = uuid4()
            self._insert_phase_history(
                conn,
                scope,
                request.cutover_operation_id,
                sequence=5,
                event_type="CUTOVER_RESUMED",
                phase="resume",
                receipt_id=receipt_id,
                request_hash=request_hash,
                authority=authority,
                occurred_at=resumed_at,
            )
            row = self._load_finalize_receipt(
                conn, scope, request.cutover_operation_id, "resume"
            )
            if row is None:
                raise EcommerceGrowthCutoverConflict("cutover resume readback is missing")
            result = self._finalize_receipt(scope, row, replayed=False)
            conn.commit()
            return result

    def prepare_validation_rollback(
        self,
        scope: TenantScope,
        request: CutoverRollbackRequest,
        *,
        actor: str,
    ) -> CutoverRollbackReceipt:
        scope, request, actor = self._validated_rollback_call(scope, request, actor)
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            existing = self._load_rollback_receipt(
                conn, scope, request.rollback_operation_id, "fence"
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EcommerceGrowthCutoverConflict(
                        "cutover rollback idempotency payload drifted"
                    )
                return self._rollback_receipt(scope, existing, replayed=True)
            duplicate = conn.execute(
                f"""SELECT cutover_operation_id,request_hash
                       FROM {self._schema}.extension_dispatch_cutover_operation
                      WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, request.idempotency_key),
            ).fetchone()
            if duplicate is not None:
                raise EcommerceGrowthCutoverConflict(
                    "cutover rollback idempotency payload drifted"
                )
            parent_request = CutoverFinalizeRequest(
                cutoverOperationId=request.activation_operation_id,
                idempotencyKey=request.idempotency_key,
                commitReceiptRef=request.commit_receipt_ref,
            )
            parent, prepare = self._load_committed_context(
                conn, scope, parent_request
            )
            if parent["status"] not in {"committed", "validated"}:
                raise EcommerceGrowthCutoverBlocked(
                    "activation is outside validation rollback window"
                )
            self._lock_final_authority(
                conn,
                scope,
                parent,
                prepare,
                resumed=False,
                check_activation_approval=False,
            )
            expected_payload = self._rollback_expected_payload(request, prepare)
            conn.execute(
                f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
                (request.approval_ref.resource_id,),
            )
            self._approval_authority(
                conn,
                scope,
                request,
                action_type_id="ecommerce_growth_cutover_rollback",
                expected_payload=expected_payload,
            )
            current = [_snapshot(dict(row)) for row in self._dispatch_rows(
                conn, scope, prepare.cutover_group_id
            )]
            fenced = [
                {
                    **item,
                    "operationFence": True,
                    "revision": int(item["revision"]) + 1,
                    "cutoverGroupRevision": prepare.target_group_revision + 1,
                }
                for item in current
            ]
            checked_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            conn.execute(
                f"""INSERT INTO {self._schema}.extension_dispatch_cutover_operation(
                     org_id,project_id,cutover_operation_id,kind,idempotency_key,request_hash,status,
                     cutover_group_id,expected_group_revision,target_group_revision,
                     target_installation_id,target_generation,target_execution_epoch,target_runtime_revision,
                     operation_ids,old_dispatch_snapshot,new_dispatch_snapshot,checkpoint,
                     occurrence_watermark,pending_target_receipt_refs,policy_ref,approval_ref,
                     requested_by,created_at,updated_at,parent_cutover_operation_id,parent_receipt_ref,
                     failure_reason)
                   VALUES(%s,%s,%s,'rollback',%s,%s,'fencing',%s,%s,%s,%s,%s,%s,%s,
                     %s,%s,%s,%s,%s,'[]'::jsonb,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    *scope.key, request.rollback_operation_id, request.idempotency_key,
                    request_hash, prepare.cutover_group_id, prepare.target_group_revision,
                    prepare.target_group_revision + 1, prepare.target_installation_id,
                    prepare.target_generation, prepare.target_execution_epoch,
                    prepare.target_runtime_revision, Jsonb(list(prepare.operation_ids)),
                    Jsonb(current), Jsonb(fenced), Jsonb(prepare.checkpoint),
                    prepare.occurrence_watermark,
                    Jsonb(prepare.policy_ref.model_dump(mode="json", by_alias=True)),
                    Jsonb(request.approval_ref.model_dump(mode="json", by_alias=True)),
                    actor, checked_at, checked_at, request.activation_operation_id,
                    Jsonb(request.commit_receipt_ref.model_dump(mode="json", by_alias=True)),
                    request.failure_reason,
                ),
            )
            try:
                updated = conn.execute(
                    f"SELECT {self._schema}.extension_dispatch_cutover_fence_rollback_ar2_016(%s,%s) AS updated",
                    (request.rollback_operation_id, actor),
                ).fetchone()["updated"]
            except psycopg.Error as exc:
                raise EcommerceGrowthCutoverBlocked(str(exc).splitlines()[0]) from exc
            if int(updated) != len(ECOMMERCE_GROWTH_OPERATIONS):
                raise EcommerceGrowthCutoverConflict("rollback fence update was not exact")
            facts = self._execution_facts(conn, scope, prepare)
            authority = self._rollback_authority(
                scope, request, prepare, phase="fence", status="draining",
                dispatch_snapshot=fenced, facts=facts, actor=actor, created_at=checked_at,
            )
            receipt_id = uuid4()
            self._insert_phase_history(
                conn, scope, request.rollback_operation_id, sequence=1,
                event_type="CUTOVER_FENCED", phase="fence", receipt_id=receipt_id,
                request_hash=request_hash, authority=authority, occurred_at=checked_at,
            )
            row = self._load_rollback_receipt(
                conn, scope, request.rollback_operation_id, "fence"
            )
            if row is None:
                raise EcommerceGrowthCutoverConflict("rollback fence readback is missing")
            result = self._rollback_receipt(scope, row, replayed=False)
            conn.commit()
            return result

    def commit_validation_rollback(
        self,
        scope: TenantScope,
        request: CutoverRollbackRequest,
        *,
        actor: str,
    ) -> CutoverRollbackReceipt:
        scope, request, actor = self._validated_rollback_call(scope, request, actor)
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._require_maintainer(conn)
            existing = self._load_rollback_receipt(
                conn, scope, request.rollback_operation_id, "rollback"
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EcommerceGrowthCutoverConflict(
                        "cutover rollback idempotency payload drifted"
                    )
                return self._rollback_receipt(scope, existing, replayed=True)
            operation = conn.execute(
                f"""SELECT * FROM {self._schema}.extension_dispatch_cutover_operation
                      WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s FOR SHARE""",
                (*scope.key, request.rollback_operation_id),
            ).fetchone()
            fence_row = self._load_rollback_receipt(
                conn, scope, request.rollback_operation_id, "fence"
            )
            if operation is None or fence_row is None:
                raise EcommerceGrowthCutoverBlocked("rollback fence authority is unavailable")
            if operation["request_hash"] != request_hash or operation["status"] != "draining":
                raise EcommerceGrowthCutoverConflict("rollback operation authority drifted")
            self._rollback_receipt(scope, fence_row, replayed=True)
            parent_request = CutoverFinalizeRequest(
                cutoverOperationId=request.activation_operation_id,
                idempotencyKey=request.idempotency_key,
                commitReceiptRef=request.commit_receipt_ref,
            )
            parent, prepare = self._load_committed_context(conn, scope, parent_request)
            conn.execute(
                f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
                (request.approval_ref.resource_id,),
            )
            self._approval_authority(
                conn,
                scope,
                request,
                action_type_id="ecommerce_growth_cutover_rollback",
                expected_payload=self._rollback_expected_payload(request, prepare),
            )
            facts = self._execution_facts(conn, scope, prepare)
            if (
                facts["claimedOccurrences"] or facts["claimedAttempts"]
                or facts["runningRuntimeAttempts"]
            ):
                raise EcommerceGrowthCutoverBlocked("rollback target execution is not drained")
            try:
                updated = conn.execute(
                    f"SELECT {self._schema}.extension_dispatch_cutover_rollback_ar2_016(%s,%s) AS updated",
                    (request.rollback_operation_id, actor),
                ).fetchone()["updated"]
            except psycopg.Error as exc:
                raise EcommerceGrowthCutoverBlocked(str(exc).splitlines()[0]) from exc
            if int(updated) != len(ECOMMERCE_GROWTH_OPERATIONS):
                raise EcommerceGrowthCutoverConflict("rollback group update was not exact")
            completed_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            drain_authority = self._rollback_authority(
                scope, request, prepare, phase="drain", status="draining",
                dispatch_snapshot=list(_array(operation["new_dispatch_snapshot"])),
                facts=facts, actor=actor, created_at=completed_at,
            )
            drain_receipt_id = uuid4()
            self._insert_phase_history(
                conn, scope, request.rollback_operation_id, sequence=2,
                event_type="CUTOVER_DRAINED", phase="drain", receipt_id=drain_receipt_id,
                request_hash=request_hash, authority=drain_authority, occurred_at=completed_at,
            )
            rows = [_snapshot(dict(row)) for row in self._dispatch_rows(
                conn, scope, prepare.cutover_group_id
            )]
            drain_ref = CutoverExactRef(
                resourceType="CutoverDrainReceipt", resourceId=str(drain_receipt_id), revision=1,
                contentHash=canonical_sha256(drain_authority),
            )
            rollback_authority = self._rollback_authority(
                scope, request, prepare, phase="rollback", status="rolled_back",
                dispatch_snapshot=rows, facts=facts, actor=actor, created_at=completed_at,
                drain_receipt_ref=drain_ref,
            )
            receipt_id = uuid4()
            self._insert_phase_history(
                conn, scope, request.rollback_operation_id, sequence=3,
                event_type="CUTOVER_ROLLED_BACK", phase="rollback", receipt_id=receipt_id,
                request_hash=request_hash, authority=rollback_authority,
                occurred_at=completed_at,
            )
            row = self._load_rollback_receipt(
                conn, scope, request.rollback_operation_id, "rollback"
            )
            if row is None:
                raise EcommerceGrowthCutoverConflict("rollback readback is missing")
            result = self._rollback_receipt(scope, row, replayed=False)
            conn.commit()
            return result

    @staticmethod
    def _validated_finalize_call(
        scope: TenantScope,
        request: CutoverFinalizeRequest,
        actor: str,
    ) -> tuple[TenantScope, CutoverFinalizeRequest, str]:
        if type(scope) is not TenantScope or type(request) is not CutoverFinalizeRequest:
            raise TypeError("trusted TenantScope and CutoverFinalizeRequest are required")
        request = CutoverFinalizeRequest.model_validate(
            request.model_dump(mode="python", by_alias=True)
        )
        if type(actor) is not str or not actor or actor != actor.strip() or len(actor) > 240:
            raise ValueError("canonical cutover actor is required")
        return scope, request, actor

    @staticmethod
    def _validated_rollback_call(
        scope: TenantScope,
        request: CutoverRollbackRequest,
        actor: str,
    ) -> tuple[TenantScope, CutoverRollbackRequest, str]:
        if type(scope) is not TenantScope or type(request) is not CutoverRollbackRequest:
            raise TypeError("trusted TenantScope and CutoverRollbackRequest are required")
        request = CutoverRollbackRequest.model_validate(
            request.model_dump(mode="python", by_alias=True)
        )
        if type(actor) is not str or not actor or actor != actor.strip() or len(actor) > 240:
            raise ValueError("canonical cutover actor is required")
        return scope, request, actor

    @staticmethod
    def _rollback_expected_payload(
        request: CutoverRollbackRequest,
        prepare: CutoverPrepareReceipt,
    ) -> dict[str, Any]:
        return {
            "activationOperationId": str(request.activation_operation_id),
            "commitReceiptRef": request.commit_receipt_ref.model_dump(
                mode="json", by_alias=True
            ),
            "cutoverGroupId": str(prepare.cutover_group_id),
            "expectedGroupRevision": prepare.target_group_revision,
            "targetInstallationId": str(prepare.target_installation_id),
            "targetGeneration": str(prepare.target_generation),
            "targetExecutionEpoch": prepare.target_execution_epoch,
            "operationIds": list(prepare.operation_ids),
        }

    @staticmethod
    def _validated_commit_call(
        scope: TenantScope,
        request: CutoverCommitRequest,
        actor: str,
    ) -> tuple[TenantScope, CutoverCommitRequest, str]:
        if type(scope) is not TenantScope or type(request) is not CutoverCommitRequest:
            raise TypeError("trusted TenantScope and CutoverCommitRequest are required")
        request = CutoverCommitRequest.model_validate(
            request.model_dump(mode="python", by_alias=True)
        )
        if type(actor) is not str or not actor or actor != actor.strip() or len(actor) > 240:
            raise ValueError("canonical cutover actor is required")
        return scope, request, actor

    def _load_operation_with_prepare(
        self,
        conn: Any,
        scope: TenantScope,
        cutover_operation_id: UUID,
    ) -> dict[str, Any]:
        row = conn.execute(
            f"""SELECT o.*,r.receipt_id,r.request_hash AS receipt_request_hash,
                        r.authority_data,r.content_hash,r.created_at AS receipt_created_at
                   FROM {self._schema}.extension_dispatch_cutover_operation o
                   JOIN {self._schema}.extension_dispatch_cutover_receipt r
                     USING(org_id,project_id,cutover_operation_id)
                  WHERE o.org_id=%s AND o.project_id=%s AND o.cutover_operation_id=%s
                    AND r.phase='prepare' FOR SHARE OF o""",
            (*scope.key, cutover_operation_id),
        ).fetchone()
        if row is None:
            raise EcommerceGrowthCutoverBlocked("cutover prepare authority is unavailable")
        return dict(row)

    def _validate_prepare_ref(
        self,
        scope: TenantScope,
        operation: dict[str, Any],
        request: CutoverCommitRequest,
    ) -> CutoverPrepareReceipt:
        prepare = self._receipt(scope, operation, replayed=True)
        if (
            request.prepare_receipt_ref.revision != 1
            or request.prepare_receipt_ref.resource_id != str(prepare.receipt_id)
            or request.prepare_receipt_ref.content_hash != prepare.content_hash
        ):
            raise EcommerceGrowthCutoverConflict("prepare Receipt reference drifted")
        reconstructed = CutoverPrepareRequest(
            cutoverOperationId=prepare.cutover_operation_id,
            idempotencyKey=operation["idempotency_key"],
            cutoverGroupId=prepare.cutover_group_id,
            expectedGroupRevision=prepare.expected_group_revision,
            targetInstallationId=prepare.target_installation_id,
            targetGeneration=prepare.target_generation,
            targetExecutionEpoch=prepare.target_execution_epoch,
            targetRuntimeRevision=prepare.target_runtime_revision,
            policyRef=prepare.policy_ref,
            approvalRef=prepare.approval_ref,
            checkpoint=prepare.checkpoint,
            occurrenceWatermark=prepare.occurrence_watermark,
            pendingTargetReceiptRefs=prepare.pending_target_receipt_refs,
            registrationReceiptRef=prepare.registration_receipt_ref,
        )
        if reconstructed.request_hash() != operation["request_hash"]:
            raise EcommerceGrowthCutoverConflict("prepared request authority drifted")
        return prepare

    @staticmethod
    def _approval_refresh_receipt(
        scope: TenantScope,
        row: dict[str, Any],
        *,
        replayed: bool,
    ) -> CutoverApprovalRefreshReceipt:
        authority = _object(row["authority_data"])
        try:
            request = CutoverApprovalRefreshRequest(
                cutoverOperationId=authority.get("cutoverOperationId"),
                idempotencyKey=row["idempotency_key"],
                prepareReceiptRef=authority.get("prepareReceiptRef"),
                approvalRef=authority.get("newApprovalRef"),
            )
        except (TypeError, ValueError) as exc:
            raise EcommerceGrowthCutoverConflict("cutover approval refresh Receipt drifted") from exc
        if (
            canonical_sha256(authority) != row["content_hash"]
            or request.request_hash() != row["request_hash"]
            or authority.get("schemaVersion")
                != "aos.ecommerce.dispatch-cutover-approval-refresh/v1"
            or authority.get("tenant")
                != {"orgId": scope.org_id, "projectId": scope.project_id}
            or authority.get("receiptId") != str(row["receipt_id"])
            or authority.get("cutoverOperationId") != str(row["cutover_operation_id"])
            or authority.get("status") != "approval_refreshed"
            or canonical_hash(authority.get("prepareReceiptRef"))
                != canonical_hash(_object(row["prepare_receipt_ref"]))
            or canonical_hash(authority.get("oldApprovalRef"))
                != canonical_hash(_object(row["old_approval_ref"]))
            or canonical_hash(authority.get("newApprovalRef"))
                != canonical_hash(_object(row["new_approval_ref"]))
            or authority.get("refreshedBy") != row["refreshed_by"]
            or authority.get("createdAt") != row["created_at"].isoformat()
        ):
            raise EcommerceGrowthCutoverConflict("cutover approval refresh Receipt drifted")
        return CutoverApprovalRefreshReceipt.model_validate({
            "tenant": authority["tenant"],
            "receiptId": row["receipt_id"],
            "cutoverOperationId": row["cutover_operation_id"],
            "prepareReceiptRef": authority["prepareReceiptRef"],
            "oldApprovalRef": authority["oldApprovalRef"],
            "newApprovalRef": authority["newApprovalRef"],
            "requestHash": row["request_hash"],
            "contentHash": row["content_hash"],
            "replayed": replayed,
            "createdAt": row["created_at"],
        })

    def _effective_approval_ref(
        self,
        conn: Any,
        scope: TenantScope,
        prepare: CutoverPrepareReceipt,
    ) -> CutoverExactRef:
        row = conn.execute(
            f"""SELECT * FROM {self._schema}.extension_dispatch_cutover_approval_refresh_receipt
                  WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s""",
            (*scope.key, prepare.cutover_operation_id),
        ).fetchone()
        if row is None:
            return prepare.approval_ref
        receipt = self._approval_refresh_receipt(scope, dict(row), replayed=True)
        if (
            receipt.old_approval_ref != prepare.approval_ref
            or receipt.prepare_receipt_ref.resource_id != str(prepare.receipt_id)
            or receipt.prepare_receipt_ref.content_hash != prepare.content_hash
        ):
            raise EcommerceGrowthCutoverConflict("cutover approval refresh origin drifted")
        return receipt.new_approval_ref

    def _lock_current_prepare_authority(
        self,
        conn: Any,
        scope: TenantScope,
        operation: dict[str, Any],
        prepare: CutoverPrepareReceipt,
        *,
        runtime_draining: bool = False,
        actor: str,
    ) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{prepare.cutover_group_id}",),
        )
        rows = self._dispatch_rows(conn, scope, prepare.cutover_group_id)
        if canonical_hash([_snapshot(dict(row)) for row in rows]) != canonical_hash(
            list(prepare.old_dispatch_snapshot)
        ):
            raise EcommerceGrowthCutoverConflict("legacy dispatch group authority drifted")
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{prepare.target_installation_id}",),
        )
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{prepare.target_installation_id}"
             f"\x1f{prepare.target_generation}",),
        )
        runtime = conn.execute(
            f"""SELECT execution_epoch,desired_state,observed_state,enabled,operation_fence,revision
                   FROM {self._schema}.extension_runtime_binding
                  WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
            (*scope.key, prepare.target_installation_id, prepare.target_generation),
        ).fetchone()
        if (
            runtime is None
            or runtime["execution_epoch"] != prepare.target_execution_epoch
            or runtime["revision"] != prepare.target_runtime_revision + int(runtime_draining)
            or runtime["desired_state"] != "enabled"
            or runtime["observed_state"] != "ready"
            or runtime["enabled"] is not (not runtime_draining)
            or runtime["operation_fence"] is not runtime_draining
        ):
            raise EcommerceGrowthCutoverConflict("target runtime binding is not exact and ready")
        approval_ref = self._effective_approval_ref(conn, scope, prepare)
        conn.execute(
            f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
            (approval_ref.resource_id,),
        )
        reconstructed = CutoverPrepareRequest(
            cutoverOperationId=prepare.cutover_operation_id,
            idempotencyKey=operation["idempotency_key"],
            cutoverGroupId=prepare.cutover_group_id,
            expectedGroupRevision=prepare.expected_group_revision,
            targetInstallationId=prepare.target_installation_id,
            targetGeneration=prepare.target_generation,
            targetExecutionEpoch=prepare.target_execution_epoch,
            targetRuntimeRevision=prepare.target_runtime_revision,
            policyRef=prepare.policy_ref,
            approvalRef=approval_ref,
            checkpoint=prepare.checkpoint,
            occurrenceWatermark=prepare.occurrence_watermark,
            pendingTargetReceiptRefs=prepare.pending_target_receipt_refs,
            registrationReceiptRef=prepare.registration_receipt_ref,
        )
        self._registration_assets(conn,scope,prepare,list(prepare.old_dispatch_snapshot),actor)
        self._approval_authority(conn, scope, reconstructed)

    def _dispatch_rows(
        self,
        conn: Any,
        scope: TenantScope,
        cutover_group_id: UUID,
    ) -> list[dict[str, Any]]:
        return conn.execute(
            f"""SELECT operation_id,handler_kind,installation_id,generation,execution_epoch,
                        operation_fence,revision,cutover_group_id,cutover_group_revision
                   FROM {self._schema}.extension_operation_dispatch_binding
                  WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
                  ORDER BY operation_id""",
            (*scope.key, cutover_group_id),
        ).fetchall()

    def _execution_facts(
        self,
        conn: Any,
        scope: TenantScope,
        prepare: CutoverPrepareReceipt,
    ) -> dict[str, Any]:
        target = (
            *scope.key,
            prepare.target_installation_id,
            prepare.target_generation,
            prepare.target_execution_epoch,
        )
        watermark = conn.execute(
            f"""SELECT max(created_at) AS watermark FROM {self._schema}.automation_occurrence
                 WHERE org_id=%s AND project_id=%s AND installation_id=%s
                   AND generation=%s AND execution_epoch=%s""",
            target,
        ).fetchone()["watermark"]
        claimed = conn.execute(
            f"""SELECT occurrence_id,claim_owner,claim_until
                   FROM {self._schema}.automation_occurrence
                  WHERE org_id=%s AND project_id=%s AND installation_id=%s
                    AND generation=%s AND execution_epoch=%s AND status='claimed'
                  ORDER BY occurrence_id""",
            target,
        ).fetchall()
        unknown = conn.execute(
            f"""SELECT a.attempt_id,a.occurrence_id,a.target_idempotency_key,a.resolved_at
                   FROM {self._schema}.automation_occurrence_dispatch_attempt a
                   JOIN {self._schema}.automation_occurrence o USING(org_id,project_id,occurrence_id)
                  WHERE a.org_id=%s AND a.project_id=%s AND o.installation_id=%s
                    AND o.generation=%s AND o.execution_epoch=%s AND a.status='unknown'
                  ORDER BY a.attempt_id""",
            target,
        ).fetchall()
        claimed_attempts = conn.execute(
            f"""SELECT a.attempt_id,a.occurrence_id,a.target_idempotency_key,
                        a.claim_owner,a.claim_until
                   FROM {self._schema}.automation_occurrence_dispatch_attempt a
                   JOIN {self._schema}.automation_occurrence o USING(org_id,project_id,occurrence_id)
                  WHERE a.org_id=%s AND a.project_id=%s AND o.installation_id=%s
                    AND o.generation=%s AND o.execution_epoch=%s AND a.status='claimed'
                  ORDER BY a.attempt_id""",
            target,
        ).fetchall()
        running = conn.execute(
            f"""SELECT attempt_id,operation_key,idempotency_key,accepted_at,lease_until
                   FROM {self._schema}.extension_runtime_execution_attempt
                  WHERE org_id=%s AND project_id=%s AND installation_id=%s
                    AND generation=%s AND execution_epoch=%s AND state='running'
                  ORDER BY attempt_id""",
            target,
        ).fetchall()
        return {
            "occurrenceWatermark": None if watermark is None else watermark.isoformat(),
            "claimedOccurrences": [
                {"occurrenceId": str(row["occurrence_id"]), "claimOwner": row["claim_owner"],
                 "claimUntil": row["claim_until"].isoformat()}
                for row in claimed
            ],
            "claimedAttempts": [
                {"attemptId": str(row["attempt_id"]), "occurrenceId": str(row["occurrence_id"]),
                 "targetIdempotencyKey": row["target_idempotency_key"],
                 "claimOwner": row["claim_owner"], "claimUntil": row["claim_until"].isoformat()}
                for row in claimed_attempts
            ],
            "unknownAttempts": [
                {"attemptId": str(row["attempt_id"]), "occurrenceId": str(row["occurrence_id"]),
                 "targetIdempotencyKey": row["target_idempotency_key"],
                 "resolvedAt": row["resolved_at"].isoformat()}
                for row in unknown
            ],
            "runningRuntimeAttempts": [
                {"attemptId": str(row["attempt_id"]), "operationKey": row["operation_key"],
                 "idempotencyKey": row["idempotency_key"],
                 "acceptedAt": row["accepted_at"].isoformat(),
                 "leaseUntil": row["lease_until"].isoformat()}
                for row in running
            ],
        }

    @staticmethod
    def _phase_authority(
        scope: TenantScope,
        request: CutoverCommitRequest,
        prepare: CutoverPrepareReceipt,
        *,
        phase: Literal["pause", "commit"],
        status: Literal["draining", "committed"],
        dispatch_snapshot: list[dict[str, Any]],
        facts: dict[str, Any],
        actor: str,
        created_at: datetime,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": f"aos.ecommerce.dispatch-cutover-{phase}/v1",
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "cutoverOperationId": str(request.cutover_operation_id),
            "phase": phase,
            "status": status,
            "cutoverGroupId": str(prepare.cutover_group_id),
            "operationIds": list(prepare.operation_ids),
            "dispatchSnapshot": dispatch_snapshot,
            **facts,
            "pendingTargetReceiptRefs": [
                item.model_dump(mode="json", by_alias=True)
                for item in prepare.pending_target_receipt_refs
            ],
            "prepareReceiptRef": request.prepare_receipt_ref.model_dump(mode="json", by_alias=True),
            "commitIdempotencyKey": request.idempotency_key,
            "requestHash": request.request_hash(),
            "claimPaused": True,
            "requestedBy": actor,
            "createdAt": created_at.isoformat(),
        }

    def _insert_phase_history(
        self,
        conn: Any,
        scope: TenantScope,
        cutover_operation_id: UUID,
        *,
        sequence: int,
        event_type: str,
        phase: str,
        receipt_id: UUID,
        request_hash: str,
        authority: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        content_hash = canonical_sha256(authority)
        event_payload = {
            "cutoverOperationId": str(cutover_operation_id),
            "phase": phase,
            "receiptId": str(receipt_id),
            "contentHash": content_hash,
        }
        conn.execute(
            f"""INSERT INTO {self._schema}.extension_dispatch_cutover_event(
                 org_id,project_id,cutover_operation_id,sequence,event_id,event_type,
                 payload,payload_hash,occurred_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (*scope.key, cutover_operation_id, sequence, uuid4(), event_type,
             Jsonb(event_payload), canonical_sha256(event_payload), occurred_at),
        )
        conn.execute(
            f"""INSERT INTO {self._schema}.extension_dispatch_cutover_receipt(
                 org_id,project_id,receipt_id,cutover_operation_id,phase,request_hash,
                 authority_data,content_hash,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (*scope.key, receipt_id, cutover_operation_id, phase, request_hash,
             Jsonb(authority), content_hash, occurred_at),
        )

    def _load_phase_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        cutover_operation_id: UUID,
        phase: str,
    ) -> dict[str, Any] | None:
        event_type, sequence = {
            "pause": ("CUTOVER_CLAIMS_PAUSED", 2),
            "commit": ("CUTOVER_COMMITTED", 3),
        }[phase]
        row = conn.execute(
            f"""SELECT r.*,o.cutover_group_id,o.operation_ids,o.old_dispatch_snapshot,
                        o.new_dispatch_snapshot,o.pending_target_receipt_refs,
                        e.payload AS event_payload,e.payload_hash,e.occurred_at
                   FROM {self._schema}.extension_dispatch_cutover_receipt r
                   JOIN {self._schema}.extension_dispatch_cutover_operation o
                     USING(org_id,project_id,cutover_operation_id)
                   JOIN {self._schema}.extension_dispatch_cutover_event e
                     USING(org_id,project_id,cutover_operation_id)
                  WHERE r.org_id=%s AND r.project_id=%s AND r.cutover_operation_id=%s
                    AND r.phase=%s AND e.sequence=%s AND e.event_type=%s""",
            (*scope.key, cutover_operation_id, phase, sequence, event_type),
        ).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _phase_receipt(
        scope: TenantScope,
        row: dict[str, Any],
        *,
        replayed: bool,
    ) -> CutoverCommitPhaseReceipt:
        authority = _object(row["authority_data"])
        event = _object(row["event_payload"])
        phase = row["phase"]
        expected_status = "draining" if phase == "pause" else "committed"
        try:
            phase_request = CutoverCommitRequest(
                cutoverOperationId=authority.get("cutoverOperationId"),
                idempotencyKey=authority.get("commitIdempotencyKey"),
                prepareReceiptRef=authority.get("prepareReceiptRef"),
            )
        except (TypeError, ValueError) as exc:
            raise EcommerceGrowthCutoverConflict(
                f"cutover {phase} Receipt authority drifted"
            ) from exc
        if (
            phase not in {"pause", "commit"}
            or canonical_sha256(authority) != row["content_hash"]
            or canonical_sha256(event) != row["payload_hash"]
            or event != {
                "cutoverOperationId": str(row["cutover_operation_id"]),
                "phase": phase,
                "receiptId": str(row["receipt_id"]),
                "contentHash": row["content_hash"],
            }
            or authority.get("tenant") != {"orgId": scope.org_id, "projectId": scope.project_id}
            or authority.get("cutoverOperationId") != str(row["cutover_operation_id"])
            or authority.get("phase") != phase
            or authority.get("status") != expected_status
            or authority.get("cutoverGroupId") != str(row["cutover_group_id"])
            or canonical_hash(authority.get("operationIds")) != canonical_hash(_array(row["operation_ids"]))
            or canonical_hash(authority.get("dispatchSnapshot")) != canonical_hash(
                _array(row["old_dispatch_snapshot"] if phase == "pause" else row["new_dispatch_snapshot"])
            )
            or canonical_hash(authority.get("pendingTargetReceiptRefs")) != canonical_hash(
                _array(row["pending_target_receipt_refs"])
            )
            or authority.get("requestHash") != row["request_hash"]
            or phase_request.request_hash() != row["request_hash"]
            or authority.get("claimPaused") is not True
            or authority.get("createdAt") != row["created_at"].isoformat()
            or row["occurred_at"] != row["created_at"]
        ):
            raise EcommerceGrowthCutoverConflict(f"cutover {phase} Receipt authority drifted")
        return CutoverCommitPhaseReceipt.model_validate({
            "tenant": authority["tenant"],
            "receiptId": row["receipt_id"],
            "cutoverOperationId": row["cutover_operation_id"],
            "phase": phase,
            "status": expected_status,
            "cutoverGroupId": authority["cutoverGroupId"],
            "operationIds": tuple(_array(authority["operationIds"])),
            "dispatchSnapshot": tuple(_array(authority["dispatchSnapshot"])),
            "occurrenceWatermark": authority.get("occurrenceWatermark"),
            "claimedOccurrences": tuple(_array(authority.get("claimedOccurrences"))),
            "claimedAttempts": tuple(_array(authority.get("claimedAttempts"))),
            "unknownAttempts": tuple(_array(authority.get("unknownAttempts"))),
            "runningRuntimeAttempts": tuple(_array(authority.get("runningRuntimeAttempts"))),
            "pendingTargetReceiptRefs": tuple(_array(authority["pendingTargetReceiptRefs"])),
            "prepareReceiptRef": authority["prepareReceiptRef"],
            "requestHash": authority["requestHash"],
            "contentHash": row["content_hash"],
            "claimPaused": True,
            "replayed": replayed,
            "createdAt": row["created_at"],
        })

    def _load_committed_context(
        self,
        conn: Any,
        scope: TenantScope,
        request: CutoverFinalizeRequest,
    ) -> tuple[dict[str, Any], CutoverPrepareReceipt]:
        operation = self._load_operation_with_prepare(
            conn, scope, request.cutover_operation_id
        )
        prepare = self._receipt(scope, operation, replayed=True)
        commit_row = self._load_phase_receipt(
            conn, scope, request.cutover_operation_id, "commit"
        )
        if commit_row is None:
            raise EcommerceGrowthCutoverBlocked("exact commit Receipt is required")
        commit = self._phase_receipt(scope, commit_row, replayed=True)
        if (
            request.commit_receipt_ref.revision != 1
            or request.commit_receipt_ref.resource_id != str(commit.receipt_id)
            or request.commit_receipt_ref.content_hash != commit.content_hash
        ):
            raise EcommerceGrowthCutoverConflict("commit Receipt reference drifted")
        return operation, prepare

    def _lock_final_authority(
        self,
        conn: Any,
        scope: TenantScope,
        operation: dict[str, Any],
        prepare: CutoverPrepareReceipt,
        *,
        resumed: bool,
        check_activation_approval: bool = True,
        actor: str | None = None,
    ) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{prepare.cutover_group_id}",),
        )
        rows = self._dispatch_rows(conn, scope, prepare.cutover_group_id)
        if canonical_hash([_snapshot(dict(row)) for row in rows]) != canonical_hash(
            list(prepare.new_dispatch_snapshot)
        ):
            raise EcommerceGrowthCutoverConflict("committed dispatch group authority drifted")
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{prepare.target_installation_id}",),
        )
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{prepare.target_installation_id}"
             f"\x1f{prepare.target_generation}",),
        )
        runtime = conn.execute(
            f"""SELECT execution_epoch,desired_state,observed_state,enabled,operation_fence,revision
                   FROM {self._schema}.extension_runtime_binding
                  WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
            (*scope.key, prepare.target_installation_id, prepare.target_generation),
        ).fetchone()
        if (
            runtime is None
            or runtime["execution_epoch"] != prepare.target_execution_epoch
            or runtime["revision"] != prepare.target_runtime_revision + (2 if resumed else 1)
            or runtime["desired_state"] != "enabled"
            or runtime["observed_state"] != "ready"
            or runtime["enabled"] is not resumed
            or runtime["operation_fence"] is resumed
        ):
            raise EcommerceGrowthCutoverConflict("target runtime finalization state drifted")
        gate = conn.execute(
            f"""SELECT cutover_operation_id,claim_paused,revision
                   FROM {self._schema}.extension_dispatch_claim_gate
                  WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s""",
            (*scope.key, prepare.cutover_group_id),
        ).fetchone()
        if (
            gate is None
            or gate["cutover_operation_id"] != prepare.cutover_operation_id
            or gate["claim_paused"] is resumed
            or int(gate["revision"]) != (2 if resumed else 1)
        ):
            raise EcommerceGrowthCutoverConflict("cutover claim gate finalization drifted")
        if not check_activation_approval:
            return
        approval_ref = self._effective_approval_ref(conn, scope, prepare)
        conn.execute(
            f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
            (approval_ref.resource_id,),
        )
        reconstructed = CutoverPrepareRequest(
            cutoverOperationId=prepare.cutover_operation_id,
            idempotencyKey=operation["idempotency_key"],
            cutoverGroupId=prepare.cutover_group_id,
            expectedGroupRevision=prepare.expected_group_revision,
            targetInstallationId=prepare.target_installation_id,
            targetGeneration=prepare.target_generation,
            targetExecutionEpoch=prepare.target_execution_epoch,
            targetRuntimeRevision=prepare.target_runtime_revision,
            policyRef=prepare.policy_ref,
            approvalRef=approval_ref,
            checkpoint=prepare.checkpoint,
            occurrenceWatermark=prepare.occurrence_watermark,
            pendingTargetReceiptRefs=prepare.pending_target_receipt_refs,
            registrationReceiptRef=prepare.registration_receipt_ref,
        )
        self._registration_assets(conn,scope,prepare,list(prepare.old_dispatch_snapshot),actor)
        self._approval_authority(conn, scope, reconstructed)

    @staticmethod
    def _finalize_authority(
        scope: TenantScope,
        request: CutoverFinalizeRequest,
        prepare: CutoverPrepareReceipt,
        *,
        phase: Literal["validate", "resume"],
        status: Literal["validated", "resumed"],
        runtime_revision: int,
        claim_paused: bool,
        facts: dict[str, Any],
        actor: str,
        created_at: datetime,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": f"aos.ecommerce.dispatch-cutover-{phase}/v1",
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "cutoverOperationId": str(request.cutover_operation_id),
            "phase": phase,
            "status": status,
            "cutoverGroupId": str(prepare.cutover_group_id),
            "operationIds": list(prepare.operation_ids),
            "dispatchSnapshot": list(prepare.new_dispatch_snapshot),
            "targetRuntimeRevision": runtime_revision,
            "claimPaused": claim_paused,
            **facts,
            "commitReceiptRef": request.commit_receipt_ref.model_dump(
                mode="json", by_alias=True
            ),
            "finalizeIdempotencyKey": request.idempotency_key,
            "requestHash": request.request_hash(),
            "requestedBy": actor,
            "createdAt": created_at.isoformat(),
        }

    def _load_finalize_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        cutover_operation_id: UUID,
        phase: Literal["validate", "resume"],
    ) -> dict[str, Any] | None:
        event_type, sequence = {
            "validate": ("CUTOVER_VALIDATED", 4),
            "resume": ("CUTOVER_RESUMED", 5),
        }[phase]
        row = conn.execute(
            f"""SELECT r.*,o.cutover_group_id,o.operation_ids,o.new_dispatch_snapshot,
                        o.target_runtime_revision,e.payload AS event_payload,
                        e.payload_hash,e.occurred_at
                   FROM {self._schema}.extension_dispatch_cutover_receipt r
                   JOIN {self._schema}.extension_dispatch_cutover_operation o
                     USING(org_id,project_id,cutover_operation_id)
                   JOIN {self._schema}.extension_dispatch_cutover_event e
                     USING(org_id,project_id,cutover_operation_id)
                  WHERE r.org_id=%s AND r.project_id=%s AND r.cutover_operation_id=%s
                    AND r.phase=%s AND e.sequence=%s AND e.event_type=%s""",
            (*scope.key, cutover_operation_id, phase, sequence, event_type),
        ).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _finalize_receipt(
        scope: TenantScope,
        row: dict[str, Any],
        *,
        replayed: bool,
    ) -> CutoverFinalizeReceipt:
        authority = _object(row["authority_data"])
        event = _object(row["event_payload"])
        phase = row["phase"]
        expected_status = "validated" if phase == "validate" else "resumed"
        expected_runtime_revision = int(row["target_runtime_revision"]) + (
            1 if phase == "validate" else 2
        )
        try:
            finalize_request = CutoverFinalizeRequest(
                cutoverOperationId=authority.get("cutoverOperationId"),
                idempotencyKey=authority.get("finalizeIdempotencyKey"),
                commitReceiptRef=authority.get("commitReceiptRef"),
            )
        except (TypeError, ValueError) as exc:
            raise EcommerceGrowthCutoverConflict(
                f"cutover {phase} Receipt authority drifted"
            ) from exc
        if (
            phase not in {"validate", "resume"}
            or canonical_sha256(authority) != row["content_hash"]
            or canonical_sha256(event) != row["payload_hash"]
            or event != {
                "cutoverOperationId": str(row["cutover_operation_id"]),
                "phase": phase,
                "receiptId": str(row["receipt_id"]),
                "contentHash": row["content_hash"],
            }
            or authority.get("tenant") != {
                "orgId": scope.org_id, "projectId": scope.project_id
            }
            or authority.get("cutoverOperationId") != str(row["cutover_operation_id"])
            or authority.get("phase") != phase
            or authority.get("status") != expected_status
            or authority.get("cutoverGroupId") != str(row["cutover_group_id"])
            or canonical_hash(authority.get("operationIds"))
                != canonical_hash(_array(row["operation_ids"]))
            or canonical_hash(authority.get("dispatchSnapshot"))
                != canonical_hash(_array(row["new_dispatch_snapshot"]))
            or authority.get("targetRuntimeRevision") != expected_runtime_revision
            or authority.get("claimPaused") is (phase == "resume")
            or authority.get("requestHash") != row["request_hash"]
            or finalize_request.request_hash() != row["request_hash"]
            or authority.get("createdAt") != row["created_at"].isoformat()
            or row["occurred_at"] != row["created_at"]
        ):
            raise EcommerceGrowthCutoverConflict(
                f"cutover {phase} Receipt authority drifted"
            )
        return CutoverFinalizeReceipt.model_validate({
            "tenant": authority["tenant"],
            "receiptId": row["receipt_id"],
            "cutoverOperationId": row["cutover_operation_id"],
            "phase": phase,
            "status": expected_status,
            "cutoverGroupId": authority["cutoverGroupId"],
            "operationIds": tuple(_array(authority["operationIds"])),
            "dispatchSnapshot": tuple(_array(authority["dispatchSnapshot"])),
            "targetRuntimeRevision": authority["targetRuntimeRevision"],
            "claimPaused": authority["claimPaused"],
            "occurrenceWatermark": authority.get("occurrenceWatermark"),
            "claimedOccurrences": tuple(_array(authority.get("claimedOccurrences"))),
            "claimedAttempts": tuple(_array(authority.get("claimedAttempts"))),
            "unknownAttempts": tuple(_array(authority.get("unknownAttempts"))),
            "runningRuntimeAttempts": tuple(
                _array(authority.get("runningRuntimeAttempts"))
            ),
            "commitReceiptRef": authority["commitReceiptRef"],
            "requestHash": authority["requestHash"],
            "contentHash": row["content_hash"],
            "replayed": replayed,
            "createdAt": row["created_at"],
        })

    @staticmethod
    def _rollback_authority(
        scope: TenantScope,
        request: CutoverRollbackRequest,
        prepare: CutoverPrepareReceipt,
        *,
        phase: Literal["fence", "drain", "rollback"],
        status: Literal["draining", "rolled_back"],
        dispatch_snapshot: list[dict[str, Any]],
        facts: dict[str, Any],
        actor: str,
        created_at: datetime,
        drain_receipt_ref: CutoverExactRef | None = None,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": f"aos.ecommerce.dispatch-cutover-rollback-{phase}/v1",
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "rollbackOperationId": str(request.rollback_operation_id),
            "activationOperationId": str(request.activation_operation_id),
            "phase": phase,
            "status": status,
            "cutoverGroupId": str(prepare.cutover_group_id),
            "operationIds": list(prepare.operation_ids),
            "dispatchSnapshot": dispatch_snapshot,
            **facts,
            "commitReceiptRef": request.commit_receipt_ref.model_dump(
                mode="json", by_alias=True
            ),
            "approvalRef": request.approval_ref.model_dump(mode="json", by_alias=True),
            "failureReason": request.failure_reason,
            "drainReceiptRef": (
                None if drain_receipt_ref is None else drain_receipt_ref.model_dump(
                    mode="json", by_alias=True
                )
            ),
            "rollbackIdempotencyKey": request.idempotency_key,
            "requestHash": request.request_hash(),
            "requestedBy": actor,
            "createdAt": created_at.isoformat(),
        }

    def _load_rollback_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        rollback_operation_id: UUID,
        phase: Literal["fence", "drain", "rollback"],
    ) -> dict[str, Any] | None:
        event_type, sequence = {
            "fence": ("CUTOVER_FENCED", 1),
            "drain": ("CUTOVER_DRAINED", 2),
            "rollback": ("CUTOVER_ROLLED_BACK", 3),
        }[phase]
        row = conn.execute(
            f"""SELECT r.*,o.operation_ids,o.old_dispatch_snapshot,o.new_dispatch_snapshot,
                        o.cutover_group_id,o.parent_cutover_operation_id,o.parent_receipt_ref,
                        o.approval_ref,o.failure_reason,o.idempotency_key,o.requested_by,
                        p.old_dispatch_snapshot AS parent_old_dispatch_snapshot,
                        e.payload AS event_payload,e.payload_hash,e.occurred_at,
                        dr.receipt_id AS drain_receipt_id,dr.content_hash AS drain_content_hash
                   FROM {self._schema}.extension_dispatch_cutover_receipt r
                   JOIN {self._schema}.extension_dispatch_cutover_operation o
                     ON o.org_id=r.org_id AND o.project_id=r.project_id
                    AND o.cutover_operation_id=r.cutover_operation_id
                   JOIN {self._schema}.extension_dispatch_cutover_operation p
                     ON p.org_id=o.org_id AND p.project_id=o.project_id
                    AND p.cutover_operation_id=o.parent_cutover_operation_id
                   JOIN {self._schema}.extension_dispatch_cutover_event e
                     ON e.org_id=r.org_id AND e.project_id=r.project_id
                    AND e.cutover_operation_id=r.cutover_operation_id
                   LEFT JOIN {self._schema}.extension_dispatch_cutover_receipt dr
                     ON dr.org_id=o.org_id AND dr.project_id=o.project_id
                    AND dr.cutover_operation_id=o.cutover_operation_id AND dr.phase='drain'
                  WHERE r.org_id=%s AND r.project_id=%s AND r.cutover_operation_id=%s
                    AND r.phase=%s AND e.sequence=%s AND e.event_type=%s""",
            (*scope.key, rollback_operation_id, phase, sequence, event_type),
        ).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _rollback_receipt(
        scope: TenantScope,
        row: dict[str, Any],
        *,
        replayed: bool,
    ) -> CutoverRollbackReceipt:
        authority = _object(row["authority_data"])
        event = _object(row["event_payload"])
        phase = row["phase"]
        expected_status = "rolled_back" if phase == "rollback" else "draining"
        if phase == "rollback":
            expected_snapshot = [
                {
                    **item,
                    "revision": int(item["revision"]) + 3,
                    "cutoverGroupRevision": int(item["cutoverGroupRevision"]) + 3,
                }
                for item in _array(row["parent_old_dispatch_snapshot"])
            ]
            expected_drain_ref: dict[str, Any] | None = {
                "resourceType": "CutoverDrainReceipt",
                "resourceId": str(row["drain_receipt_id"]),
                "revision": 1,
                "contentHash": row["drain_content_hash"],
            }
        else:
            expected_snapshot = _array(row["new_dispatch_snapshot"])
            expected_drain_ref = None
        try:
            rollback_request = CutoverRollbackRequest(
                rollbackOperationId=authority.get("rollbackOperationId"),
                idempotencyKey=authority.get("rollbackIdempotencyKey"),
                activationOperationId=authority.get("activationOperationId"),
                commitReceiptRef=authority.get("commitReceiptRef"),
                approvalRef=authority.get("approvalRef"),
                failureReason=authority.get("failureReason"),
            )
        except (TypeError, ValueError) as exc:
            raise EcommerceGrowthCutoverConflict(
                f"cutover rollback {phase} Receipt authority drifted"
            ) from exc
        if (
            phase not in {"fence", "drain", "rollback"}
            or canonical_sha256(authority) != row["content_hash"]
            or canonical_sha256(event) != row["payload_hash"]
            or event != {
                "cutoverOperationId": str(row["cutover_operation_id"]),
                "phase": phase,
                "receiptId": str(row["receipt_id"]),
                "contentHash": row["content_hash"],
            }
            or authority.get("tenant") != {
                "orgId": scope.org_id, "projectId": scope.project_id
            }
            or authority.get("rollbackOperationId") != str(row["cutover_operation_id"])
            or authority.get("activationOperationId")
                != str(row["parent_cutover_operation_id"])
            or authority.get("phase") != phase
            or authority.get("status") != expected_status
            or authority.get("cutoverGroupId") != str(row["cutover_group_id"])
            or canonical_hash(authority.get("operationIds"))
                != canonical_hash(_array(row["operation_ids"]))
            or canonical_hash(authority.get("dispatchSnapshot"))
                != canonical_hash(expected_snapshot)
            or canonical_hash(authority.get("commitReceiptRef"))
                != canonical_hash(_object(row["parent_receipt_ref"]))
            or canonical_hash(authority.get("approvalRef"))
                != canonical_hash(_object(row["approval_ref"]))
            or authority.get("failureReason") != row["failure_reason"]
            or canonical_hash(authority.get("drainReceiptRef"))
                != canonical_hash(expected_drain_ref)
            or authority.get("rollbackIdempotencyKey") != row["idempotency_key"]
            or authority.get("requestHash") != row["request_hash"]
            or rollback_request.request_hash() != row["request_hash"]
            or authority.get("requestedBy") != row["requested_by"]
            or authority.get("createdAt") != row["created_at"].isoformat()
            or row["occurred_at"] != row["created_at"]
        ):
            raise EcommerceGrowthCutoverConflict(
                f"cutover rollback {phase} Receipt authority drifted"
            )
        return CutoverRollbackReceipt.model_validate({
            "tenant": authority["tenant"],
            "receiptId": row["receipt_id"],
            "rollbackOperationId": row["cutover_operation_id"],
            "activationOperationId": row["parent_cutover_operation_id"],
            "phase": phase,
            "status": expected_status,
            "cutoverGroupId": authority["cutoverGroupId"],
            "operationIds": tuple(_array(authority["operationIds"])),
            "dispatchSnapshot": tuple(_array(authority["dispatchSnapshot"])),
            "occurrenceWatermark": authority.get("occurrenceWatermark"),
            "claimedOccurrences": tuple(_array(authority.get("claimedOccurrences"))),
            "claimedAttempts": tuple(_array(authority.get("claimedAttempts"))),
            "unknownAttempts": tuple(_array(authority.get("unknownAttempts"))),
            "runningRuntimeAttempts": tuple(
                _array(authority.get("runningRuntimeAttempts"))
            ),
            "commitReceiptRef": authority["commitReceiptRef"],
            "approvalRef": authority["approvalRef"],
            "failureReason": authority["failureReason"],
            "drainReceiptRef": authority.get("drainReceiptRef"),
            "requestHash": authority["requestHash"],
            "contentHash": row["content_hash"],
            "replayed": replayed,
            "createdAt": row["created_at"],
        })

    def _approval_authority(
        self,
        conn: Any,
        scope: TenantScope,
        request: Any,
        *,
        action_type_id: str = "ecommerce_growth_cutover",
        expected_payload: dict[str, Any] | None = None,
    ) -> datetime:
        # AIP tenant RLS is owned by the runtime role.  A formally registered
        # cutover runs through the protected identity carrying both roles, so
        # use the tenant-scoped reader before restoring the maintainer role in
        # the current-approval validator.  Legacy callers keep their established
        # connection role and therefore preserve the pre-registration contract.
        if self._registration_service is not None:
            conn.execute("SET LOCAL ROLE aos_runtime")
        approval = conn.execute(
            f"""SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
                      actor_id,reason,expires_at,created_at,action_binding_hash
                 FROM {self._schema}.aip_action_approval_event
                WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
            (*scope.key, request.approval_ref.resource_id),
        ).fetchone()
        if (
            approval is None
            or int(approval["proposal_version"]) != request.approval_ref.revision
            or approval["decision"] != "approved"
        ):
            raise EcommerceGrowthCutoverBlocked("active exact cutover ActionApprovalEvent is required")
        if canonical_hash(dict(approval), prefixed=True) != request.approval_ref.content_hash:
            raise EcommerceGrowthCutoverConflict("cutover ActionApprovalEvent hash drifted")
        proposal = conn.execute(
            f"""SELECT proposal_id,action_type_id,action_type_snapshot,task_id,run_id,
                      object_ref,purpose,risk_level,policy_snapshot,payload,diff,evidence_refs,
                      impact_preview_id,impact_preview_revision,impact_preview_hash,
                      action_binding_hash,source_draft_id,source_draft_revision,source_draft_hash,
                      approval_policy_hash,proposal_hash,status,version,expires_at,created_by
                 FROM {self._schema}.aip_action_proposal
                WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, approval["proposal_id"]),
        ).fetchone()
        payload = _object(proposal["payload"]) if proposal is not None else {}
        draft = conn.execute(
            f"""SELECT proposal_hash,snapshot FROM {self._schema}.aip_action_draft
                 WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, approval["proposal_id"]),
        ).fetchone()
        stable = _object(draft["snapshot"]) if draft is not None else {}
        checked_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        impact_preview_ref = (
            {
                "resourceType": "ImpactPreviewRevision",
                "resourceId": proposal["impact_preview_id"],
                "revision": proposal["impact_preview_revision"],
                "contentHash": proposal["impact_preview_hash"],
            }
            if proposal is not None and proposal["impact_preview_id"] is not None else None
        )
        source_draft_ref = (
            {
                "resourceType": "ActionDraftRevision",
                "resourceId": proposal["source_draft_id"],
                "revision": proposal["source_draft_revision"],
                "contentHash": proposal["source_draft_hash"],
            }
            if proposal is not None and proposal["source_draft_id"] is not None else None
        )
        if (
            proposal is None
            or proposal["expires_at"] <= checked_at
            or (approval["expires_at"] is not None and approval["expires_at"] <= checked_at)
        ):
            raise EcommerceGrowthCutoverBlocked(
                "active exact cutover ActionApprovalEvent is required"
            )
        expected = expected_payload or {
            "cutoverGroupId": str(request.cutover_group_id),
            "expectedGroupRevision": request.expected_group_revision,
            "targetInstallationId": str(request.target_installation_id),
            "targetGeneration": str(request.target_generation),
            "targetExecutionEpoch": request.target_execution_epoch,
            "targetRuntimeRevision": request.target_runtime_revision,
            "operationIds": list(sorted(ECOMMERCE_GROWTH_OPERATIONS)),
            "policyRef": request.policy_ref.model_dump(mode="json", by_alias=True),
        }
        if expected_payload is None and request.registration_receipt_ref is not None:
            expected["registrationReceiptRef"] = request.registration_receipt_ref.model_dump(mode="json")
        if (
            proposal is None
            or proposal["action_type_id"] != action_type_id
            or draft is None
            or proposal["status"] != "approved"
            or proposal["proposal_hash"] != approval["proposal_hash"]
            or draft["proposal_hash"] != proposal["proposal_hash"]
            or canonical_hash(stable) != proposal["proposal_hash"]
            or stable.get("tenantScope") != {
                "orgId": scope.org_id, "projectId": scope.project_id
            }
            or stable.get("createdBy") != proposal["created_by"]
            or canonical_hash(stable.get("actionType"))
                != canonical_hash(_object(proposal["action_type_snapshot"]))
            or stable.get("taskId") != proposal["task_id"]
            or stable.get("runId") != proposal["run_id"]
            or canonical_hash(stable.get("objectRef")) != canonical_hash(proposal["object_ref"])
            or stable.get("purpose") != proposal["purpose"]
            or stable.get("riskLevel") != proposal["risk_level"]
            or canonical_hash(stable.get("policy"))
                != canonical_hash(_object(proposal["policy_snapshot"]))
            or stable.get("approvalPolicyHash") != proposal["approval_policy_hash"]
            or (proposal["impact_preview_id"] is None)
                != (proposal["impact_preview_revision"] is None)
            or (proposal["impact_preview_id"] is None)
                != (proposal["impact_preview_hash"] is None)
            or (proposal["source_draft_id"] is None)
                != (proposal["source_draft_revision"] is None)
            or (proposal["source_draft_id"] is None)
                != (proposal["source_draft_hash"] is None)
            or canonical_hash(stable.get("payload")) != canonical_hash(payload)
            or canonical_hash(stable.get("diff"))
                != canonical_hash(_object(proposal["diff"]))
            or canonical_hash(stable.get("evidenceRefs"))
                != canonical_hash(_array(proposal["evidence_refs"]))
            or canonical_hash(stable.get("impactPreviewRef"))
                != canonical_hash(impact_preview_ref)
            or canonical_hash(stable.get("sourceDraftRef"))
                != canonical_hash(source_draft_ref)
            or stable.get("expiresAt") != proposal["expires_at"].isoformat()
            or stable.get("actionBindingHash") != proposal["action_binding_hash"]
            or not proposal["action_binding_hash"]
            or proposal["action_binding_hash"] != approval["action_binding_hash"]
            or any(canonical_hash(payload.get(key)) != canonical_hash(value) for key, value in expected.items())
        ):
            raise EcommerceGrowthCutoverBlocked("cutover approval is not bound to this exact group")
        if self._registration_service is not None:
            from aos_api.ecommerce_growth_cutover_current_approval import require_current_cutover_approval
            require_current_cutover_approval(conn=conn, scope=scope, proposal=proposal,
                approval_id=approval['approval_event_id'], checked_at=checked_at, schema=self._schema)
            conn.execute("SET LOCAL ROLE aos_extension_maintainer")
        return checked_at

    def _registration_assets(self,conn,scope,target,old_snapshot,actor):
        ref=target.registration_receipt_ref
        if ref is None:
            return
        if self._registration_service is None:
            raise EcommerceGrowthCutoverBlocked("first registration activation is not wired")
        conn.execute("SET LOCAL ROLE aos_runtime")
        result=self._registration_service.validate_cutover_registration_assets_in_transaction(
            conn,scope=scope,actor=actor,receipt_ref=ref,dispatch_snapshot=old_snapshot,
            installation_id=str(target.target_installation_id),generation=str(target.target_generation),
            execution_epoch=target.target_execution_epoch,binding_revision=target.target_runtime_revision)
        if (type(result) is not dict or result.get("receiptRef")!=ref.model_dump(mode="json")
                or result.get("currentConfigurationValidated") is not True
                or result.get("currentReleaseValidated") is not True
                or result.get("runtimeStateValidated") is not False
                or result.get("executable") is not False):
            raise EcommerceGrowthCutoverBlocked("current registration assets were not validated")
        conn.execute("SET LOCAL ROLE aos_extension_maintainer")

    @staticmethod
    def _require_maintainer(conn: Any) -> None:
        row = conn.execute(
            """SELECT current_user AS current_role,
                      current_setting('transaction_isolation') AS isolation_level,
                      pg_has_role(session_user,'aos_extension_maintainer','member') AS member,
                      EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=session_user
                        AND (rolsuper OR rolbypassrls)) AS privileged"""
        ).fetchone()
        if (
            row is None
            or row["current_role"] != "aos_extension_maintainer"
            or row["isolation_level"] != "serializable"
            or row["member"] is not True
            or row["privileged"] is not False
        ):
            raise EcommerceGrowthCutoverBlocked("dedicated non-privileged cutover maintainer is required")

    @staticmethod
    def _receipt(
        scope: TenantScope,
        row: dict[str, Any],
        *,
        replayed: bool,
    ) -> CutoverPrepareReceipt:
        authority = _object(row["authority_data"])
        stored_watermark = (
            row["occurrence_watermark"].isoformat()
            if row["occurrence_watermark"] is not None else None
        )
        if (
            canonical_sha256(authority) != row["content_hash"]
            or authority.get("tenant") != {
                "orgId": scope.org_id, "projectId": scope.project_id
            }
            or authority.get("cutoverOperationId") != str(row["cutover_operation_id"])
            or authority.get("requestHash") != row["request_hash"]
            or row["receipt_request_hash"] != row["request_hash"]
            or authority.get("status") != "prepared"
            or row["kind"] != "activate"
            or authority.get("cutoverGroupId") != str(row["cutover_group_id"])
            or authority.get("expectedGroupRevision") != row["expected_group_revision"]
            or authority.get("targetGroupRevision") != row["target_group_revision"]
            or authority.get("targetInstallationId") != str(row["target_installation_id"])
            or authority.get("targetGeneration") != str(row["target_generation"])
            or authority.get("targetExecutionEpoch") != row["target_execution_epoch"]
            or authority.get("targetRuntimeRevision") != row["target_runtime_revision"]
            or canonical_hash(authority.get("operationIds"))
                != canonical_hash(_array(row["operation_ids"]))
            or canonical_hash(authority.get("oldDispatchSnapshot"))
                != canonical_hash(_array(row["old_dispatch_snapshot"]))
            or canonical_hash(authority.get("newDispatchSnapshot"))
                != canonical_hash(_array(row["new_dispatch_snapshot"]))
            or canonical_hash(authority.get("checkpoint"))
                != canonical_hash(_object(row["checkpoint"]))
            or authority.get("occurrenceWatermark") != stored_watermark
            or canonical_hash(authority.get("pendingTargetReceiptRefs"))
                != canonical_hash(_array(row["pending_target_receipt_refs"]))
            or canonical_hash(authority.get("policyRef"))
                != canonical_hash(_object(row["policy_ref"]))
            or canonical_hash(authority.get("approvalRef"))
                != canonical_hash(_object(row["approval_ref"]))
            or authority.get("requestedBy") != row["requested_by"]
            or authority.get("createdAt") != row["created_at"].isoformat()
            or authority.get("createdAt") != row["receipt_created_at"].isoformat()
        ):
            raise EcommerceGrowthCutoverConflict("cutover prepare Receipt authority drifted")
        return CutoverPrepareReceipt.model_validate({
            "tenant": authority["tenant"],
            "receiptId": row["receipt_id"],
            "cutoverOperationId": row["cutover_operation_id"],
            "status": "prepared",
            "cutoverGroupId": authority["cutoverGroupId"],
            "expectedGroupRevision": authority["expectedGroupRevision"],
            "targetGroupRevision": authority["targetGroupRevision"],
            "targetInstallationId": authority["targetInstallationId"],
            "targetGeneration": authority["targetGeneration"],
            "targetExecutionEpoch": authority["targetExecutionEpoch"],
            "targetRuntimeRevision": authority["targetRuntimeRevision"],
            "operationIds": tuple(_array(authority["operationIds"])),
            "oldDispatchSnapshot": tuple(_array(authority["oldDispatchSnapshot"])),
            "newDispatchSnapshot": tuple(_array(authority["newDispatchSnapshot"])),
            "checkpoint": _object(authority["checkpoint"]),
            "occurrenceWatermark": authority["occurrenceWatermark"],
            "pendingTargetReceiptRefs": tuple(_array(authority["pendingTargetReceiptRefs"])),
            "registrationReceiptRef": authority.get("registrationReceiptRef"),
            "policyRef": authority["policyRef"],
            "approvalRef": authority["approvalRef"],
            "requestHash": authority["requestHash"],
            "contentHash": row["content_hash"],
            "replayed": replayed,
            "createdAt": row["receipt_created_at"],
        })


__all__ = [
    "CutoverCommitPhaseReceipt",
    "CutoverCommitRequest",
    "CutoverPrepareReceipt",
    "CutoverPrepareRequest",
    "CutoverRollbackReceipt",
    "CutoverRollbackRequest",
    "CutoverExactRef",
    "CutoverFinalizeReceipt",
    "CutoverFinalizeRequest",
    "EcommerceGrowthCutoverBlocked",
    "EcommerceGrowthCutoverConflict",
    "EcommerceGrowthCutoverError",
    "EcommerceGrowthCutoverStore",
]
