"""Canonical PostgreSQL authority for AIP runtime guard policies."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, TypeVar
from urllib.parse import urlparse

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevision,
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevision,
    EgressPolicyRevisionCreate,
    GuardPolicyLifecycle,
    RegionState,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
CreateT = TypeVar("CreateT", EgressPolicyRevisionCreate, DataClassificationPolicyRevisionCreate)
RevisionT = TypeVar("RevisionT", EgressPolicyRevision, DataClassificationPolicyRevision)


class GuardPolicyStoreError(RuntimeError):
    code = "AIP_RUNTIME_GUARD_POLICY_STORE_ERROR"


class GuardPolicyNotFound(GuardPolicyStoreError):
    code = "AIP_RUNTIME_GUARD_POLICY_NOT_FOUND"


class GuardPolicyConflict(GuardPolicyStoreError):
    code = "AIP_RUNTIME_GUARD_POLICY_VERSION_CONFLICT"


class GuardPolicyIdempotencyConflict(GuardPolicyStoreError):
    code = "AIP_RUNTIME_GUARD_POLICY_IDEMPOTENCY_CONFLICT"


class GuardPolicyDependencyBlocked(GuardPolicyStoreError):
    code = "AIP_DEPENDENCY_BLOCKED"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def materialize_policy(
    scope: TenantScope,
    actor: str,
    item: CreateT,
    *,
    created_at: datetime | None = None,
) -> EgressPolicyRevision | DataClassificationPolicyRevision:
    content = item.model_dump(mode="json", by_alias=True)
    model = EgressPolicyRevision if isinstance(item, EgressPolicyRevisionCreate) else DataClassificationPolicyRevision
    return model.model_validate(
        {
            **content,
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "contentHash": canonical_hash(content),
            "createdBy": actor,
            "createdAt": created_at or datetime.now(UTC),
        }
    )


class AipRuntimeGuardPolicyStore:
    _SPECS = {
        "egress": (EgressPolicyRevisionCreate, EgressPolicyRevision, "EgressPolicyRevision"),
        "data_classification": (
            DataClassificationPolicyRevisionCreate,
            DataClassificationPolicyRevision,
            "DataClassificationPolicyRevision",
        ),
    }

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish_egress(self, scope: TenantScope, actor: str, key: str, item: EgressPolicyRevisionCreate, *, expected_version: int = 0) -> EgressPolicyRevision:
        return self._publish("egress", scope, actor, key, item, expected_version)

    def publish_data_classification(self, scope: TenantScope, actor: str, key: str, item: DataClassificationPolicyRevisionCreate, *, expected_version: int = 0) -> DataClassificationPolicyRevision:
        return self._publish("data_classification", scope, actor, key, item, expected_version)

    def get_egress(self, scope: TenantScope, policy_id: str, revision: int | None = None) -> EgressPolicyRevision:
        return self._get("egress", scope, policy_id, revision)

    def get_data_classification(self, scope: TenantScope, policy_id: str, revision: int | None = None) -> DataClassificationPolicyRevision:
        return self._get("data_classification", scope, policy_id, revision)

    def require_exact_active(
        self,
        scope: TenantScope,
        ref: VersionedAssetRef,
        *,
        now: datetime | None = None,
    ) -> EgressPolicyRevision | DataClassificationPolicyRevision:
        kind = {
            "EgressPolicyRevision": "egress",
            "DataClassificationPolicyRevision": "data_classification",
        }.get(ref.asset_type)
        if kind is None:
            raise GuardPolicyDependencyBlocked("unsupported runtime guard policy ref")
        try:
            item = self._get(kind, scope, ref.asset_id, ref.revision)
        except GuardPolicyNotFound:
            raise GuardPolicyDependencyBlocked("exact runtime guard policy is unavailable") from None
        if item.content_hash != ref.content_hash:
            raise GuardPolicyDependencyBlocked("runtime guard policy exact ref drifted")
        instant = now or datetime.now(UTC)
        if item.lifecycle is not GuardPolicyLifecycle.ACTIVE:
            raise GuardPolicyDependencyBlocked("runtime guard policy is not active")
        if not (item.effective_from <= instant < item.effective_until):
            raise GuardPolicyDependencyBlocked("runtime guard policy is outside effective window")
        if isinstance(item, EgressPolicyRevision):
            if item.region_state is not RegionState.CONFIRMED or not item.region:
                raise GuardPolicyDependencyBlocked("egress region is not confirmed")
            if (
                item.allowed_schemes != ["https"]
                or item.allowed_hosts != ["apihub.agnes-ai.com"]
                or item.allowed_ports != [443]
                or item.allow_public_fallback
                or item.unknown_destination_behavior != "block"
            ):
                raise GuardPolicyDependencyBlocked("egress policy is outside approved boundary")
        return item

    def require_provider_dependencies(self, scope: TenantScope, provider: Any) -> None:
        egress = self.require_exact_active(scope, provider.egress_policy_ref)
        self.require_exact_active(scope, provider.data_classification_policy_ref)
        if not isinstance(egress, EgressPolicyRevision):
            raise GuardPolicyDependencyBlocked("provider egress ref resolved to wrong policy kind")
        endpoint = urlparse(str(provider.endpoint_profile.base_url))
        port = endpoint.port or (443 if endpoint.scheme == "https" else None)
        if (
            endpoint.scheme not in egress.allowed_schemes
            or endpoint.hostname not in egress.allowed_hosts
            or port not in egress.allowed_ports
        ):
            raise GuardPolicyDependencyBlocked("provider endpoint is outside exact egress policy")
        if provider.endpoint_profile.region != egress.region:
            raise GuardPolicyDependencyBlocked("provider region does not match exact egress policy")

    def _publish(self, kind: str, scope: TenantScope, actor: str, key: str, item: CreateT, expected_version: int) -> RevisionT:
        request_hash = canonical_hash(
            {"expectedVersion": expected_version, "revision": item.model_dump(mode="json", by_alias=True)}
        )
        operation = f"runtime_guard_policy.{kind}.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay:
                return self._get(kind, scope, replay["resourceId"], int(replay["revision"]), conn=conn)
            head = conn.execute(
                "SELECT current_revision,version FROM aip_runtime_guard_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s FOR UPDATE",
                (*scope.key, kind, item.policy_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise GuardPolicyConflict("stale runtime guard policy head version")
            next_revision = int(head["current_revision"]) + 1 if head else 1
            if item.revision != next_revision:
                raise GuardPolicyConflict("revision is not the next runtime guard policy revision")
            result = materialize_policy(scope, actor, item)
            if head:
                conn.execute(
                    "UPDATE aip_runtime_guard_policy_head SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s",
                    (result.revision, *scope.key, kind, result.policy_id),
                )
            else:
                conn.execute(
                    "INSERT INTO aip_runtime_guard_policy_head(org_id,project_id,policy_kind,policy_id,current_revision,version) "
                    "VALUES(%s,%s,%s,%s,%s,1)",
                    (*scope.key, kind, result.policy_id, result.revision),
                )
            conn.execute(
                """INSERT INTO aip_runtime_guard_policy_revision(
                org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
                effective_from,effective_until,payload,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    *scope.key,
                    kind,
                    result.policy_id,
                    result.revision,
                    result.content_hash,
                    result.lifecycle.value,
                    result.effective_from,
                    result.effective_until,
                    self._json(result.model_dump(mode="json", by_alias=True)),
                    actor,
                    result.created_at,
                ),
            )
            result_ref = {
                "resourceType": self._SPECS[kind][2],
                "resourceId": result.policy_id,
                "revision": result.revision,
                "contentHash": result.content_hash,
            }
            conn.execute(
                """INSERT INTO aip_runtime_guard_policy_receipt(
                org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (
                    *scope.key,
                    f"aip10g-{uuid.uuid4().hex[:20]}",
                    operation,
                    key,
                    request_hash,
                    self._json(result_ref),
                    actor,
                ),
            )
            conn.commit()
            return self._get(kind, scope, result.policy_id, result.revision, conn=conn)

    def _get(self, kind: str, scope: TenantScope, policy_id: str, revision: int | None = None, *, conn: Any | None = None) -> RevisionT:
        model = self._SPECS[kind][1]

        def read(connection: Any) -> RevisionT:
            target = revision
            if target is None:
                head = connection.execute(
                    "SELECT current_revision FROM aip_runtime_guard_policy_head "
                    "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s",
                    (*scope.key, kind, policy_id),
                ).fetchone()
                if not head:
                    raise GuardPolicyNotFound("runtime guard policy not found")
                target = int(head["current_revision"])
            row = connection.execute(
                "SELECT payload FROM aip_runtime_guard_policy_revision "
                "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s AND revision=%s",
                (*scope.key, kind, policy_id, target),
            ).fetchone()
            if not row:
                raise GuardPolicyNotFound("runtime guard policy revision not found")
            return model.model_validate(self._load(row["payload"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def _replay(self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT request_hash,result_ref FROM aip_runtime_guard_policy_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise GuardPolicyIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value
