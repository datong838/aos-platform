"""Canonical PostgreSQL authority for exact tenant network policies."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_network_policy_contracts import NetworkPolicyRevision, NetworkPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevision
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    GuardPolicyDependencyBlocked,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class NetworkPolicyStoreError(RuntimeError):
    code = "AIP_NETWORK_POLICY_STORE_ERROR"


class NetworkPolicyNotFound(NetworkPolicyStoreError):
    code = "AIP_NETWORK_POLICY_NOT_FOUND"


class NetworkPolicyConflict(NetworkPolicyStoreError):
    code = "AIP_NETWORK_POLICY_VERSION_CONFLICT"


class NetworkPolicyIdempotencyConflict(NetworkPolicyStoreError):
    code = "AIP_NETWORK_POLICY_IDEMPOTENCY_CONFLICT"


class NetworkPolicyDependencyBlocked(NetworkPolicyStoreError):
    code = "AIP_DEPENDENCY_BLOCKED"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def materialize_policy(
    scope: TenantScope,
    actor: str,
    item: NetworkPolicyRevisionCreate,
    *,
    created_at: datetime | None = None,
) -> NetworkPolicyRevision:
    content = item.model_dump(mode="json", by_alias=True)
    return NetworkPolicyRevision.model_validate({
        **content,
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "contentHash": canonical_hash(content),
        "createdBy": actor,
        "createdAt": created_at or datetime.now(UTC),
    })


class AipNetworkPolicyStore:
    def __init__(self, connect_factory: ConnectFactory | None = None, *, guard_policy_store=None) -> None:
        self._connect_factory = connect_factory or db_connect
        self._guard_policy_store = guard_policy_store or AipRuntimeGuardPolicyStore(
            connect_factory or db_connect
        )

    def publish(self, scope: TenantScope, actor: str, key: str, item: NetworkPolicyRevisionCreate, *, expected_version: int = 0) -> NetworkPolicyRevision:
        request_hash = canonical_hash({
            "expectedVersion": expected_version,
            "revision": item.model_dump(mode="json", by_alias=True),
        })
        operation = "network_policy.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay:
                return self.get(scope, replay["resourceId"], int(replay["revision"]), conn=conn)
            self._require_egress(scope, item)
            head = conn.execute(
                "SELECT current_revision,version FROM aip_network_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s FOR UPDATE",
                (*scope.key, item.policy_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise NetworkPolicyConflict("stale network policy head version")
            next_revision = int(head["current_revision"]) + 1 if head else 1
            if item.revision != next_revision:
                raise NetworkPolicyConflict("revision is not the next network policy revision")
            result = materialize_policy(scope, actor, item)
            if head:
                conn.execute(
                    "UPDATE aip_network_policy_head SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                    (result.revision, *scope.key, result.policy_id),
                )
            else:
                conn.execute(
                    "INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
                    "VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, result.policy_id, result.revision),
                )
            conn.execute(
                """INSERT INTO aip_network_policy_revision(
                org_id,project_id,policy_id,revision,content_hash,lifecycle,
                effective_from,effective_until,payload,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (*scope.key, result.policy_id, result.revision, result.content_hash,
                 result.lifecycle.value, result.effective_from, result.effective_until,
                 self._json(result.model_dump(mode="json", by_alias=True)), actor, result.created_at),
            )
            result_ref = {
                "resourceType": "NetworkPolicyRevision",
                "resourceId": result.policy_id,
                "revision": result.revision,
                "contentHash": result.content_hash,
            }
            conn.execute(
                """INSERT INTO aip_network_policy_receipt(
                org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (*scope.key, f"aip10n-{uuid.uuid4().hex[:20]}", operation, key,
                 request_hash, self._json(result_ref), actor),
            )
            conn.commit()
            return self.get(scope, result.policy_id, result.revision, conn=conn)

    def get(self, scope: TenantScope, policy_id: str, revision: int | None = None, *, conn=None) -> NetworkPolicyRevision:
        def read(connection) -> NetworkPolicyRevision:
            target = revision
            if target is None:
                head = connection.execute(
                    "SELECT current_revision FROM aip_network_policy_head "
                    "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                    (*scope.key, policy_id),
                ).fetchone()
                if not head:
                    raise NetworkPolicyNotFound("network policy not found")
                target = int(head["current_revision"])
            row = connection.execute(
                "SELECT payload FROM aip_network_policy_revision "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s",
                (*scope.key, policy_id, target),
            ).fetchone()
            if not row:
                raise NetworkPolicyNotFound("network policy revision not found")
            return NetworkPolicyRevision.model_validate(self._load(row["payload"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def require_exact_active(self, scope: TenantScope, ref: VersionedAssetRef, *, now: datetime | None = None) -> NetworkPolicyRevision:
        if ref.asset_type != "NetworkPolicyRevision":
            raise NetworkPolicyDependencyBlocked("unsupported network policy ref")
        try:
            item = self.get(scope, ref.asset_id, ref.revision)
        except NetworkPolicyNotFound:
            raise NetworkPolicyDependencyBlocked("exact network policy is unavailable") from None
        instant = now or datetime.now(UTC)
        if item.content_hash != ref.content_hash:
            raise NetworkPolicyDependencyBlocked("network policy exact ref drifted")
        if item.lifecycle.value != "active":
            raise NetworkPolicyDependencyBlocked("network policy is not active")
        if not (item.effective_from <= instant < item.effective_until):
            raise NetworkPolicyDependencyBlocked("network policy is outside effective window")
        self._require_egress(scope, item, now=instant)
        return item

    def require_runtime_policy_dependency(self, scope: TenantScope, policy: Any) -> NetworkPolicyRevision:
        network = self.require_exact_active(scope, policy.network_policy_ref)
        if network.egress_policy_ref != policy.egress_policy_ref:
            raise NetworkPolicyDependencyBlocked("network and runtime policy egress refs do not match")
        return network

    def _require_egress(self, scope: TenantScope, item: NetworkPolicyRevisionCreate | NetworkPolicyRevision, *, now: datetime | None = None) -> EgressPolicyRevision:
        try:
            egress = self._guard_policy_store.require_exact_active(
                scope, item.egress_policy_ref, now=now
            )
        except GuardPolicyDependencyBlocked as exc:
            raise NetworkPolicyDependencyBlocked(str(exc)) from None
        if not isinstance(egress, EgressPolicyRevision):
            raise NetworkPolicyDependencyBlocked("network egress ref resolved to wrong policy kind")
        if item.effective_from < egress.effective_from or item.effective_until > egress.effective_until:
            raise NetworkPolicyDependencyBlocked("network policy window exceeds egress policy")
        if set(item.allowed_schemes) - set(egress.allowed_schemes):
            raise NetworkPolicyDependencyBlocked("network scheme exceeds egress policy")
        if set(item.allowed_hosts) - set(egress.allowed_hosts):
            raise NetworkPolicyDependencyBlocked("network host exceeds egress policy")
        if set(item.allowed_ports) - set(egress.allowed_ports):
            raise NetworkPolicyDependencyBlocked("network port exceeds egress policy")
        return egress

    def _replay(self, conn, scope, operation, key, request_hash):
        row = conn.execute(
            "SELECT request_hash,result_ref FROM aip_network_policy_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise NetworkPolicyIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value
