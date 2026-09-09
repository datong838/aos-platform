"""Trusted host authority for atomic ecommerce growth dispatch cutover."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, StrictInt, field_validator, model_validator
from psycopg.types.json import Jsonb

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope


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
        return canonical_sha256(self.model_dump(mode="json", by_alias=True))


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
    policy_ref: CutoverExactRef
    approval_ref: CutoverExactRef
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

    def __init__(self, connect_factory: ConnectFactory, *, schema: str = "public") -> None:
        if not callable(connect_factory):
            raise TypeError("dedicated cutover maintainer connection is required")
        if re.fullmatch(r"[a-z_][a-z0-9_]*", schema) is None:
            raise ValueError("cutover schema is invalid")
        self._connect_factory = connect_factory
        self._schema = schema

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
                or row["operation_fence"] is not False
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

            conn.execute(
                f"SELECT {self._schema}.extension_dispatch_cutover_lock_approval_ar2_013(%s)",
                (request.approval_ref.resource_id,),
            )
            checked_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            self._approval_authority(conn, scope, request, checked_at)
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

    def _approval_authority(
        self,
        conn: Any,
        scope: TenantScope,
        request: CutoverPrepareRequest,
        checked_at: datetime,
    ) -> None:
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
            or (approval["expires_at"] is not None and approval["expires_at"] <= checked_at)
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
        expected = {
            "cutoverGroupId": str(request.cutover_group_id),
            "expectedGroupRevision": request.expected_group_revision,
            "targetInstallationId": str(request.target_installation_id),
            "targetGeneration": str(request.target_generation),
            "targetExecutionEpoch": request.target_execution_epoch,
            "targetRuntimeRevision": request.target_runtime_revision,
            "operationIds": list(sorted(ECOMMERCE_GROWTH_OPERATIONS)),
            "policyRef": request.policy_ref.model_dump(mode="json", by_alias=True),
        }
        if (
            proposal is None
            or proposal["action_type_id"] != "ecommerce_growth_cutover"
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
            "policyRef": authority["policyRef"],
            "approvalRef": authority["approvalRef"],
            "requestHash": authority["requestHash"],
            "contentHash": row["content_hash"],
            "replayed": replayed,
            "createdAt": row["receipt_created_at"],
        })


__all__ = [
    "CutoverPrepareReceipt",
    "CutoverPrepareRequest",
    "CutoverExactRef",
    "EcommerceGrowthCutoverBlocked",
    "EcommerceGrowthCutoverConflict",
    "EcommerceGrowthCutoverError",
    "EcommerceGrowthCutoverStore",
]
