"""Subordinate ecommerce dispatch lifecycle bound to an authorized runtime disable."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_dispatch_configuration_receipt import decode_receipt
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope


class EcommerceGrowthLifecycleError(RuntimeError):
    pass


class EcommerceGrowthLifecycleBlocked(EcommerceGrowthLifecycleError):
    pass


class EcommerceGrowthLifecycleConflict(EcommerceGrowthLifecycleError):
    pass


class DispatchLifecycleReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: UUID
    runtime_operation_id: UUID
    activation_operation_id: UUID
    phase: Literal["fence", "detach"]
    status: Literal["fenced", "detached"]
    operation_ids: tuple[str, ...]
    dispatch_snapshot: tuple[dict[str, Any], ...]
    unknown_attempts: tuple[dict[str, Any], ...]
    configuration_refresh_ref: PipelineExactRef | None = None
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replayed: bool = False


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if type(value) is not dict:
        raise EcommerceGrowthLifecycleConflict("dispatch lifecycle authority is invalid")
    return value


def _array(value: Any) -> list[Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if type(value) is not list:
        raise EcommerceGrowthLifecycleConflict("dispatch lifecycle array is invalid")
    return value


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "operationId": row["operation_id"],
        "handlerKind": row["handler_kind"],
        "installationId": None
        if row["installation_id"] is None
        else str(row["installation_id"]),
        "generation": None if row["generation"] is None else str(row["generation"]),
        "executionEpoch": row["execution_epoch"],
        "operationFence": row["operation_fence"],
        "revision": row["revision"],
        "cutoverGroupId": str(row["cutover_group_id"]),
        "cutoverGroupRevision": row["cutover_group_revision"],
    }


class EcommerceGrowthDisableDependent:
    """Run inside the two existing disable transactions; never commits on its own."""

    def __init__(self, *, schema: str = "public") -> None:
        if not schema or not schema.replace("_", "").isalnum():
            raise ValueError("canonical lifecycle schema is required")
        self._schema = schema

    def after_runtime_fenced(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        runtime_operation_id: UUID,
    ) -> DispatchLifecycleReceipt | None:
        _require_transaction(conn)
        scope = self._scope(conn, org_id, project_id)
        runtime = self._runtime_operation(conn, scope, runtime_operation_id)
        existing = self._load_receipt(conn, scope, runtime_operation_id, "fence")
        if existing is not None:
            return self._receipt(scope, existing, replayed=True)
        activations = conn.execute(
            f"""SELECT c.*,b.revision AS current_binding_revision,
                            b.execution_epoch AS current_binding_epoch
                   FROM {self._schema}.extension_dispatch_cutover_operation c
                   JOIN {self._schema}.extension_runtime_binding b
                     ON b.org_id=c.org_id AND b.project_id=c.project_id
                    AND b.installation_id=c.target_installation_id
                    AND b.generation=c.target_generation
                  WHERE c.org_id=%s AND c.project_id=%s AND c.kind='activate'
                    AND c.status='resumed' AND c.target_installation_id=%s
                    AND b.execution_epoch>c.target_execution_epoch
                    AND NOT b.enabled AND b.operation_fence
                    AND b.observed_state='draining'""",
            (*scope.key, runtime["installation_id"]),
        ).fetchall()
        matched = []
        for row in activations:
            candidate = dict(row)
            target_revision, target_epoch, refresh_ref = self._current_dispatch_authority(
                conn, scope, candidate
            )
            if (
                (
                    refresh_ref is None
                    and int(candidate["current_binding_revision"])
                    == int(runtime["expected_binding_revision"]) + 1
                )
                or (
                    refresh_ref is not None
                    and int(runtime["expected_binding_revision"]) == target_revision
                    and int(candidate["current_binding_revision"]) == target_revision + 1
                )
            ) and int(candidate["current_binding_epoch"]) > target_epoch:
                candidate["configuration_refresh_ref"] = refresh_ref
                matched.append(candidate)
        activations = matched
        if not activations:
            attached = conn.execute(
                f"""SELECT 1 FROM {self._schema}.extension_operation_dispatch_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s LIMIT 1""",
                (*scope.key, runtime["installation_id"]),
            ).fetchone()
            if attached is not None:
                raise EcommerceGrowthLifecycleConflict("attached dispatch has no exact disable activation")
            return None
        if len(activations) != 1:
            raise EcommerceGrowthLifecycleConflict(
                "runtime disable matches multiple resumed activations"
            )
        activation = dict(activations[0])
        refresh_ref = activation.pop("configuration_refresh_ref")
        current = self._dispatch_rows(conn, scope, activation["cutover_group_id"])
        fenced = [
            {
                **item,
                "operationFence": True,
                "revision": int(item["revision"]) + 1,
                "cutoverGroupRevision": int(item["cutoverGroupRevision"]) + 1,
            }
            for item in current
        ]
        legacy = _array(activation["old_dispatch_snapshot"])
        request_hash = canonical_sha256(
            {
                "runtimeOperationId": str(runtime_operation_id),
                "runtimeRequestHash": runtime["request_hash"],
                "activationOperationId": str(activation["cutover_operation_id"]),
                "activationRequestHash": activation["request_hash"],
                "operationIds": _array(activation["operation_ids"]),
            }
        )
        checked_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        conn.execute(
            f"""INSERT INTO {self._schema}.extension_dispatch_lifecycle_operation(
                 org_id,project_id,runtime_operation_id,activation_operation_id,
                 cutover_group_id,status,request_hash,operation_ids,extension_snapshot,
                 fenced_snapshot,legacy_snapshot,fenced_group_revision,requested_by,
                 created_at,updated_at)
               VALUES(%s,%s,%s,%s,%s,'fencing',%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                runtime_operation_id,
                activation["cutover_operation_id"],
                activation["cutover_group_id"],
                request_hash,
                Jsonb(_array(activation["operation_ids"])),
                Jsonb(current),
                Jsonb(fenced),
                Jsonb(legacy),
                int(current[0]["cutoverGroupRevision"]) + 1,
                runtime["requested_by"],
                checked_at,
                checked_at,
            ),
        )
        try:
            updated = conn.execute(
                f"SELECT {self._schema}.extension_dispatch_lifecycle_fence_ar2_017(%s,%s) AS updated",
                (runtime_operation_id, runtime["requested_by"]),
            ).fetchone()["updated"]
        except psycopg.Error as exc:
            raise EcommerceGrowthLifecycleBlocked(str(exc).splitlines()[0]) from exc
        if int(updated) != len(ECOMMERCE_GROWTH_OPERATIONS):
            raise EcommerceGrowthLifecycleConflict("dispatch lifecycle fence was not exact")
        authority = self._authority(
            scope,
            runtime,
            activation,
            phase="fence",
            dispatch_snapshot=fenced,
            request_hash=request_hash,
            unknown_attempts=self._unknown_attempts(conn, scope, activation),
            configuration_refresh_ref=refresh_ref,
        )
        self._insert_history(
            conn,
            scope,
            runtime_operation_id,
            phase="fence",
            sequence=1,
            event_type="DISPATCH_DISABLE_FENCED",
            authority=authority,
            request_hash=request_hash,
            occurred_at=checked_at,
        )
        row = self._load_receipt(conn, scope, runtime_operation_id, "fence")
        if row is None:
            raise EcommerceGrowthLifecycleConflict("dispatch fence Receipt is missing")
        return self._receipt(scope, row, replayed=False)

    def after_runtime_disabled(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        runtime_operation_id: UUID,
    ) -> DispatchLifecycleReceipt | None:
        _require_transaction(conn)
        scope = self._scope(conn, org_id, project_id)
        existing = self._load_receipt(conn, scope, runtime_operation_id, "detach")
        if existing is not None:
            return self._receipt(scope, existing, replayed=True)
        lifecycle = conn.execute(
            f"""SELECT * FROM {self._schema}.extension_dispatch_lifecycle_operation
                  WHERE org_id=%s AND project_id=%s AND runtime_operation_id=%s FOR UPDATE""",
            (*scope.key, runtime_operation_id),
        ).fetchone()
        if lifecycle is None:
            return None
        lifecycle = dict(lifecycle)
        fence = self._load_receipt(conn, scope, runtime_operation_id, "fence")
        if fence is None or lifecycle["status"] != "fenced":
            raise EcommerceGrowthLifecycleBlocked("dispatch lifecycle fence is unavailable")
        self._receipt(scope, fence, replayed=True)
        runtime = self._runtime_operation(conn, scope, runtime_operation_id)
        activation = conn.execute(
            f"""SELECT * FROM {self._schema}.extension_dispatch_cutover_operation
                  WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s""",
            (*scope.key, lifecycle["activation_operation_id"]),
        ).fetchone()
        if activation is None:
            raise EcommerceGrowthLifecycleConflict("activation authority is missing")
        activation = dict(activation)
        target_revision, _target_epoch, refresh_ref = self._current_dispatch_authority(
            conn, scope, activation
        )
        if (
            refresh_ref is not None
            and int(runtime["expected_binding_revision"]) != target_revision
        ):
            raise EcommerceGrowthLifecycleConflict(
                "runtime disable differs from current dispatch authority"
            )
        try:
            updated = conn.execute(
                f"SELECT {self._schema}.extension_dispatch_lifecycle_detach_ar2_017(%s,%s) AS updated",
                (runtime_operation_id, runtime["requested_by"]),
            ).fetchone()["updated"]
        except psycopg.Error as exc:
            raise EcommerceGrowthLifecycleBlocked(str(exc).splitlines()[0]) from exc
        if int(updated) != len(ECOMMERCE_GROWTH_OPERATIONS):
            raise EcommerceGrowthLifecycleConflict("dispatch lifecycle detach was not exact")
        detached = self._dispatch_rows(conn, scope, lifecycle["cutover_group_id"])
        request_hash = lifecycle["request_hash"]
        completed_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        authority = self._authority(
            scope,
            runtime,
            activation,
            phase="detach",
            dispatch_snapshot=detached,
            request_hash=request_hash,
            unknown_attempts=self._unknown_attempts(conn, scope, activation),
            fence_receipt=fence,
            configuration_refresh_ref=refresh_ref,
        )
        self._insert_history(
            conn,
            scope,
            runtime_operation_id,
            phase="detach",
            sequence=2,
            event_type="DISPATCH_DISABLED_DETACHED",
            authority=authority,
            request_hash=request_hash,
            occurred_at=completed_at,
        )
        row = self._load_receipt(conn, scope, runtime_operation_id, "detach")
        if row is None:
            raise EcommerceGrowthLifecycleConflict("dispatch detach Receipt is missing")
        return self._receipt(scope, row, replayed=False)

    def _scope(self, conn: Any, org_id: str, project_id: str) -> TenantScope:
        scope = TenantScope(org_id, project_id)
        actual = conn.execute(
            """SELECT current_setting('aos.org_id',true) AS org_id,
                      current_setting('aos.project_id',true) AS project_id"""
        ).fetchone()
        if actual is None or (actual["org_id"], actual["project_id"]) != scope.key:
            raise PermissionError("dispatch lifecycle tenant scope mismatch")
        return scope

    def _runtime_operation(
        self, conn: Any, scope: TenantScope, runtime_operation_id: UUID
    ) -> dict[str, Any]:
        row = conn.execute(
            f"""SELECT * FROM {self._schema}.extension_runtime_operation
                  WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",
            (*scope.key, UUID(str(runtime_operation_id))),
        ).fetchone()
        if row is None or row["kind"] != "disable":
            raise EcommerceGrowthLifecycleBlocked("exact runtime disable operation is required")
        return dict(row)

    def _dispatch_rows(
        self, conn: Any, scope: TenantScope, cutover_group_id: UUID
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"""SELECT * FROM {self._schema}.extension_operation_dispatch_binding
                  WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
                  ORDER BY operation_id""",
            (*scope.key, cutover_group_id),
        ).fetchall()
        return [_snapshot(dict(row)) for row in rows]

    def _unknown_attempts(
        self, conn: Any, scope: TenantScope, activation: dict[str, Any]
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"""SELECT a.attempt_id,a.occurrence_id,a.target_idempotency_key,a.resolved_at
                   FROM {self._schema}.automation_occurrence_dispatch_attempt a
                   JOIN {self._schema}.automation_occurrence o
                     USING(org_id,project_id,occurrence_id)
                  WHERE a.org_id=%s AND a.project_id=%s AND a.status='unknown'
                    AND o.installation_id=%s AND o.generation=%s
                  ORDER BY a.attempt_id""",
            (
                *scope.key,
                activation["target_installation_id"],
                activation["target_generation"],
            ),
        ).fetchall()
        return [
            {
                "attemptId": str(row["attempt_id"]),
                "occurrenceId": str(row["occurrence_id"]),
                "targetIdempotencyKey": row["target_idempotency_key"],
                "resolvedAt": row["resolved_at"].isoformat(),
            }
            for row in rows
        ]

    def _current_dispatch_authority(
        self, conn: Any, scope: TenantScope, activation: dict[str, Any]
    ) -> tuple[int, int, dict[str, Any] | None]:
        refresh_table = conn.execute(
            "SELECT to_regclass(%s) AS relation",
            (f"{self._schema}.extension_dispatch_configuration_refresh_receipt",),
        ).fetchone()
        if refresh_table is None or refresh_table["relation"] is None:
            return (
                int(activation["target_runtime_revision"]),
                int(activation["target_execution_epoch"]),
                None,
            )
        row = conn.execute(
            f"""SELECT *
                   FROM {self._schema}.extension_dispatch_configuration_refresh_receipt
                  WHERE org_id=%s AND project_id=%s AND activation_operation_id=%s
                  ORDER BY revision DESC LIMIT 1""",
            (*scope.key, activation["cutover_operation_id"]),
        ).fetchone()
        if row is None:
            return (
                int(activation["target_runtime_revision"]),
                int(activation["target_execution_epoch"]),
                None,
            )
        try:
            decoded = decode_receipt(dict(row))
        except ValueError as exc:
            raise EcommerceGrowthLifecycleConflict(
                "current configuration refresh authority drifted"
            ) from exc
        request = decoded["request"]
        if (
            request["orgId"] != scope.org_id
            or request["projectId"] != scope.project_id
            or request["installationRef"]["installationId"]
            != str(activation["target_installation_id"])
            or request["generation"] != str(activation["target_generation"])
            or request["cutoverGroupId"] != str(activation["cutover_group_id"])
        ):
            raise EcommerceGrowthLifecycleConflict(
                "configuration refresh differs from activation root"
            )
        return (
            int(request["targetRuntimeRevision"]),
            int(request["targetExecutionEpoch"]),
            decoded["ref"],
        )

    @staticmethod
    def _authority(
        scope: TenantScope,
        runtime: dict[str, Any],
        activation: dict[str, Any],
        *,
        phase: Literal["fence", "detach"],
        dispatch_snapshot: list[dict[str, Any]],
        request_hash: str,
        unknown_attempts: list[dict[str, Any]],
        fence_receipt: dict[str, Any] | None = None,
        configuration_refresh_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": f"aos.ecommerce.dispatch-disable-{phase}/v1",
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "runtimeOperationId": str(runtime["operation_id"]),
            "activationOperationId": str(activation["cutover_operation_id"]),
            "phase": phase,
            "status": "fenced" if phase == "fence" else "detached",
            "operationIds": _array(activation["operation_ids"]),
            "dispatchSnapshot": dispatch_snapshot,
            "unknownAttempts": unknown_attempts,
            "configurationRefreshRef": configuration_refresh_ref,
            "runtimeRequestHash": runtime["request_hash"],
            "requestHash": request_hash,
            "requestedBy": runtime["requested_by"],
            "fenceReceiptRef": None
            if fence_receipt is None
            else {
                "resourceType": "DispatchDisableFenceReceipt",
                "resourceId": str(fence_receipt["receipt_id"]),
                "revision": 1,
                "contentHash": fence_receipt["content_hash"],
            },
        }

    def _insert_history(
        self,
        conn: Any,
        scope: TenantScope,
        runtime_operation_id: UUID,
        *,
        phase: Literal["fence", "detach"],
        sequence: int,
        event_type: str,
        authority: dict[str, Any],
        request_hash: str,
        occurred_at: Any,
    ) -> None:
        receipt_id = uuid4()
        content_hash = canonical_sha256(authority)
        event = {
            "runtimeOperationId": str(runtime_operation_id),
            "phase": phase,
            "receiptId": str(receipt_id),
            "contentHash": content_hash,
        }
        conn.execute(
            f"""INSERT INTO {self._schema}.extension_dispatch_lifecycle_receipt(
                 org_id,project_id,receipt_id,runtime_operation_id,phase,request_hash,
                 authority_data,content_hash,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                receipt_id,
                runtime_operation_id,
                phase,
                request_hash,
                Jsonb(authority),
                content_hash,
                occurred_at,
            ),
        )
        conn.execute(
            f"""INSERT INTO {self._schema}.extension_dispatch_lifecycle_event(
                 org_id,project_id,runtime_operation_id,sequence,event_type,payload,
                 payload_hash,occurred_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                runtime_operation_id,
                sequence,
                event_type,
                Jsonb(event),
                canonical_sha256(event),
                occurred_at,
            ),
        )

    def _load_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        runtime_operation_id: UUID,
        phase: Literal["fence", "detach"],
    ) -> dict[str, Any] | None:
        sequence, event_type = (1, "DISPATCH_DISABLE_FENCED") if phase == "fence" else (
            2,
            "DISPATCH_DISABLED_DETACHED",
        )
        row = conn.execute(
            f"""SELECT r.*,l.activation_operation_id,l.operation_ids,l.status,
                        e.payload AS event_payload,e.payload_hash
                   FROM {self._schema}.extension_dispatch_lifecycle_receipt r
                   JOIN {self._schema}.extension_dispatch_lifecycle_operation l
                     ON l.org_id=r.org_id AND l.project_id=r.project_id
                    AND l.runtime_operation_id=r.runtime_operation_id
                   JOIN {self._schema}.extension_dispatch_lifecycle_event e
                     ON e.org_id=r.org_id AND e.project_id=r.project_id
                    AND e.runtime_operation_id=r.runtime_operation_id
                  WHERE r.org_id=%s AND r.project_id=%s AND r.runtime_operation_id=%s
                    AND r.phase=%s AND e.sequence=%s AND e.event_type=%s""",
            (*scope.key, runtime_operation_id, phase, sequence, event_type),
        ).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _receipt(
        scope: TenantScope, row: dict[str, Any], *, replayed: bool
    ) -> DispatchLifecycleReceipt:
        authority = _object(row["authority_data"])
        event = _object(row["event_payload"])
        expected_status = "fenced" if row["phase"] == "fence" else "detached"
        if (
            canonical_sha256(authority) != row["content_hash"]
            or canonical_sha256(event) != row["payload_hash"]
            or event
            != {
                "runtimeOperationId": str(row["runtime_operation_id"]),
                "phase": row["phase"],
                "receiptId": str(row["receipt_id"]),
                "contentHash": row["content_hash"],
            }
            or authority.get("tenant")
            != {"orgId": scope.org_id, "projectId": scope.project_id}
            or authority.get("runtimeOperationId") != str(row["runtime_operation_id"])
            or authority.get("activationOperationId")
            != str(row["activation_operation_id"])
            or authority.get("phase") != row["phase"]
            or authority.get("status") != expected_status
            or authority.get("operationIds") != _array(row["operation_ids"])
            or authority.get("requestHash") != row["request_hash"]
        ):
            raise EcommerceGrowthLifecycleConflict(
                f"dispatch lifecycle {row['phase']} Receipt authority drifted"
            )
        return DispatchLifecycleReceipt.model_validate(
            {
                "tenant": authority["tenant"],
                "receiptId": row["receipt_id"],
                "runtimeOperationId": row["runtime_operation_id"],
                "activationOperationId": row["activation_operation_id"],
                "phase": row["phase"],
                "status": expected_status,
                "operationIds": tuple(authority["operationIds"]),
                "dispatchSnapshot": tuple(authority["dispatchSnapshot"]),
                "unknownAttempts": tuple(authority["unknownAttempts"]),
                "configurationRefreshRef": authority.get("configurationRefreshRef"),
                "requestHash": authority["requestHash"],
                "contentHash": row["content_hash"],
                "replayed": replayed,
            }
        )


__all__ = [
    "DispatchLifecycleReceipt",
    "EcommerceGrowthDisableDependent",
    "EcommerceGrowthLifecycleBlocked",
    "EcommerceGrowthLifecycleConflict",
    "EcommerceGrowthLifecycleError",
]
