"""Lock current Route subject heads for one final proof; never grant release."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationProof,
    canonical_route_eval_finalization_proof,
)
from aos_api.aip_model_route_eval_manifest import (
    CONTEXT_DOMAIN,
    RouteEvalApplication,
    _canonical,
    _parse_context,
)
from aos_api.aip_model_route_eval_signatures import _manifest
from aos_api.aip_model_route_eval_subject_binding import _stored
from aos_api.aip_model_runtime_contracts import (
    ModelEvalCandidate,
    ModelRouteRevision,
    ModelRuntimeLifecycle,
    RegisteredModelRevision,
    RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.tenant_scope import TenantScope

SESSION = "aos_model_route_eval"


class RouteEvalCurrentSubjectRejected(RuntimeError):
    """Safe fail-closed category without persisted payloads or credentials."""


@dataclass(frozen=True)
class VerifiedRouteEvalCurrentSubject:
    execution_id: str
    manifest_hash: str
    source_ref: VersionedAssetRef
    target_ref: VersionedAssetRef
    expected_head_version: int
    model_refs: tuple[VersionedAssetRef, ...]
    runtime_policy_ref: VersionedAssetRef
    checked_at: datetime
    caller_xid: str
    caller_pid: int
    execution_allowed: bool = False


def _boundary(conn, scope: TenantScope) -> dict:
    from aos_api.aip_model_route_eval_owner import _require_native_connection

    _require_native_connection(conn)
    row = conn.execute(
        """SELECT pg_catalog.current_database() AS database,
            (SELECT oid FROM pg_catalog.pg_database
              WHERE datname=pg_catalog.current_database()) AS database_oid,
            session_user AS login,current_user AS role,
            pg_catalog.current_setting('aos.org_id',true) AS org_id,
            pg_catalog.current_setting('aos.project_id',true) AS project_id,
            pg_catalog.current_setting('transaction_isolation') AS isolation,
            pg_catalog.current_setting('transaction_read_only') AS readonly,
            pg_catalog.pg_current_xact_id()::text AS xid,
            pg_catalog.pg_backend_pid() AS pid,pg_catalog.clock_timestamp() AS now"""
    ).fetchone()
    if (
        type(row) is not dict
        or type(row.get("database")) is not str
        or re.fullmatch(r"[a-z][a-z0-9_]{0,62}", row["database"]) is None
        or type(row.get("database_oid")) is not int
        or row["database_oid"] < 1
        or type(row.get("login")) is not str
        or row["login"] != SESSION
        or (
            row.get("role"),
            row.get("org_id"),
            row.get("project_id"),
            row.get("isolation"),
            row.get("readonly"),
        )
        != ("aos_runtime", *scope.key, "serializable", "off")
        or type(row.get("xid")) is not str
        or not row["xid"].isascii()
        or not row["xid"].isdecimal()
        or row["xid"].startswith("0")
        or type(row.get("pid")) is not int
        or row["pid"] < 1
        or type(row.get("now")) is not datetime
        or row["now"].utcoffset() is None
    ):
        raise ValueError("exact current Route subject caller required")
    return row


def _same_boundary(before: dict, after: dict) -> bool:
    return all(after.get(key) == value for key, value in before.items() if key != "now")


def _lock_model(conn, scope: TenantScope, expected: RegisteredModelRevision) -> None:
    row = conn.execute(
        """SELECT h.version,r.registered_model_id AS asset_id,r.revision,
            r.content_hash,r.lifecycle,r.payload
            FROM public.aip_registered_model_head h
            JOIN public.aip_registered_model_revision r
              ON r.org_id=h.org_id AND r.project_id=h.project_id
             AND r.registered_model_id=h.registered_model_id
             AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s
              AND h.registered_model_id=%s AND r.revision=%s
            FOR SHARE OF h""",
        (*scope.key, expected.registered_model_id, expected.revision),
    ).fetchone()
    if (
        type(row) is not dict
        or type(row.get("version")) is not int
        or isinstance(row.get("version"), bool)
        or row.get("asset_id") != expected.registered_model_id
        or type(row.get("revision")) is not int
        or isinstance(row.get("revision"), bool)
        or row.get("revision") != expected.revision
        or row.get("content_hash") != expected.content_hash
        or row.get("lifecycle") != ModelRuntimeLifecycle.ACTIVE.value
        or type(row.get("payload")) is not dict
    ):
        raise ValueError("current Route model head required")
    parsed = RegisteredModelRevision.model_validate(row["payload"])
    if (
        parsed != expected
        or _canonical(row["payload"])
        != _canonical(expected.model_dump(mode="json", by_alias=True))
        or _stored(scope, parsed) != row["payload"]
    ):
        raise ValueError("current Route model payload required")


def _lock_policy(conn, scope: TenantScope, expected: RuntimePolicyRevision) -> None:
    row = conn.execute(
        """SELECT h.version,r.runtime_policy_id AS asset_id,r.revision,
            r.content_hash,r.lifecycle,r.payload
            FROM public.aip_runtime_policy_head h
            JOIN public.aip_runtime_policy_revision r
              ON r.org_id=h.org_id AND r.project_id=h.project_id
             AND r.runtime_policy_id=h.runtime_policy_id
             AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s
              AND h.runtime_policy_id=%s AND r.revision=%s
            FOR SHARE OF h""",
        (*scope.key, expected.policy_id, expected.revision),
    ).fetchone()
    if (
        type(row) is not dict
        or type(row.get("version")) is not int
        or isinstance(row.get("version"), bool)
        or row.get("asset_id") != expected.policy_id
        or type(row.get("revision")) is not int
        or isinstance(row.get("revision"), bool)
        or row.get("revision") != expected.revision
        or row.get("content_hash") != expected.content_hash
        or row.get("lifecycle") != ModelRuntimeLifecycle.ACTIVE.value
        or type(row.get("payload")) is not dict
    ):
        raise ValueError("current Route policy head required")
    parsed = RuntimePolicyRevision.model_validate(row["payload"])
    if (
        parsed != expected
        or parsed.kill_switch_enabled
        or _canonical(row["payload"])
        != _canonical(expected.model_dump(mode="json", by_alias=True))
        or _stored(scope, parsed) != row["payload"]
    ):
        raise ValueError("current Route policy payload required")


def read_current_route_eval_subject(
    conn,
    *,
    scope: TenantScope,
    proof: RouteEvalFinalizationProof,
    manifest_bytes: bytes,
) -> VerifiedRouteEvalCurrentSubject:
    """Lock current Route/config heads in the caller transaction.

    Issuer/revocation, Source, Report/cost and release authority remain separate
    mandatory gates.  This function never commits, retries or opens a connection.
    """
    try:
        if (
            type(scope) is not TenantScope
            or scope.key != ("org-org", "dev-project")
            or type(proof) is not RouteEvalFinalizationProof
            or (proof.tenant.org_id, proof.tenant.project_id) != scope.key
            or type(manifest_bytes) is not bytes
            or hashlib.sha256(manifest_bytes).hexdigest() != proof.manifest_hash
        ):
            raise ValueError
        canonical_route_eval_finalization_proof(proof)
        body = _manifest(manifest_bytes)
        if "routeApplication" not in body or "modelPlan" in body:
            raise ValueError
        context, source, claim, _, _, models = _parse_context(
            CONTEXT_DOMAIN + _canonical(body["context"])
        )
        app = RouteEvalApplication.model_validate(body["routeApplication"])
        if (
            type(source) is not ModelRouteRevision
            or type(claim) is not ModelEvalCandidate
            or (source.tenant.org_id, source.tenant.project_id) != scope.key
            or not proof.execution_id == body["executionId"] == app.execution_id
            or proof.context_binding_hash != body["contextBindingHash"]
            or app.context_binding_hash != proof.context_binding_hash
            or any(item.signed_case.claim.subject_kind != "ModelRouteRevision" for item in proof.calls)
        ):
            raise ValueError

        before = _boundary(conn, scope)
        store = AipModelRuntimeStore()
        current = store.require_current_route_eval_candidate_for_update(
            conn,
            scope,
            claim.source_ref,
            claim.target_ref,
            expected_head_version=claim.expected_head_version,
        )
        if current != claim:
            raise ValueError

        indexed: dict[str, RegisteredModelRevision] = {}
        for model in (*models, app.judge_model):
            if type(model) is not RegisteredModelRevision:
                raise ValueError
            original = indexed.get(model.registered_model_id)
            if original is not None and original != model:
                raise ValueError
            indexed[model.registered_model_id] = model
        expected_refs = {
            identifier: VersionedAssetRef(
                assetType="RegisteredModelRevision",
                assetId=identifier,
                revision=model.revision,
                contentHash=model.content_hash,
            )
            for identifier, model in indexed.items()
        }
        if any(expected_refs.get(call.model_ref.asset_id) != call.model_ref for call in app.calls):
            raise ValueError
        for identifier in sorted(indexed):
            _lock_model(conn, scope, indexed[identifier])

        policy = RuntimePolicyRevision.model_validate(
            context["subject"]["runtimePolicy"]
        )
        if (
            source.runtime_policy_ref
            != VersionedAssetRef(
                assetType="RuntimePolicyRevision",
                assetId=policy.policy_id,
                revision=policy.revision,
                contentHash=policy.content_hash,
            )
        ):
            raise ValueError
        _lock_policy(conn, scope, policy)

        after = _boundary(conn, scope)
        if (
            not _same_boundary(before, after)
            or after["now"] < before["now"]
            or after["now"] < proof.finalized_at
            or after["now"] >= app.expires_at
        ):
            raise ValueError
        return VerifiedRouteEvalCurrentSubject(
            execution_id=proof.execution_id,
            manifest_hash=proof.manifest_hash,
            source_ref=claim.source_ref,
            target_ref=claim.target_ref,
            expected_head_version=claim.expected_head_version,
            model_refs=tuple(expected_refs[key] for key in sorted(expected_refs)),
            runtime_policy_ref=source.runtime_policy_ref,
            checked_at=after["now"],
            caller_xid=after["xid"],
            caller_pid=after["pid"],
        )
    except RouteEvalCurrentSubjectRejected:
        raise
    except Exception as exc:
        raise RouteEvalCurrentSubjectRejected(
            "current Route Eval subject required"
        ) from exc


__all__ = [
    "RouteEvalCurrentSubjectRejected",
    "VerifiedRouteEvalCurrentSubject",
    "read_current_route_eval_subject",
]
