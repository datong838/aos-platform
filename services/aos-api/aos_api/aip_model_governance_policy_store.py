"""Canonical PostgreSQL authority for model quota and budget policies."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, TypeVar

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_budget_store import AipBudgetAuthorityStore, BudgetNotFound
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevision,
    BudgetPolicyRevisionCreate,
    ModelGovernancePolicyLifecycle,
    QuotaPolicyRevision,
    QuotaPolicyRevisionCreate,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
CreateT = TypeVar("CreateT", QuotaPolicyRevisionCreate, BudgetPolicyRevisionCreate)
RevisionT = TypeVar("RevisionT", QuotaPolicyRevision, BudgetPolicyRevision)


class ModelGovernancePolicyStoreError(RuntimeError):
    code = "AIP_MODEL_GOVERNANCE_POLICY_STORE_ERROR"


class ModelGovernancePolicyNotFound(ModelGovernancePolicyStoreError):
    code = "AIP_MODEL_GOVERNANCE_POLICY_NOT_FOUND"


class ModelGovernancePolicyConflict(ModelGovernancePolicyStoreError):
    code = "AIP_MODEL_GOVERNANCE_POLICY_VERSION_CONFLICT"


class ModelGovernancePolicyIdempotencyConflict(ModelGovernancePolicyStoreError):
    code = "AIP_MODEL_GOVERNANCE_POLICY_IDEMPOTENCY_CONFLICT"


class ModelGovernancePolicyDependencyBlocked(ModelGovernancePolicyStoreError):
    code = "AIP_DEPENDENCY_BLOCKED"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def materialize_policy(scope: TenantScope, actor: str, item: CreateT, *, created_at: datetime | None = None):
    content = item.model_dump(mode="json", by_alias=True)
    model = QuotaPolicyRevision if isinstance(item, QuotaPolicyRevisionCreate) else BudgetPolicyRevision
    return model.model_validate({
        **content,
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "contentHash": canonical_hash(content),
        "createdBy": actor,
        "createdAt": created_at or datetime.now(UTC),
    })


class AipModelGovernancePolicyStore:
    _SPECS = {
        "quota": (QuotaPolicyRevisionCreate, QuotaPolicyRevision, "QuotaPolicyRevision"),
        "budget": (BudgetPolicyRevisionCreate, BudgetPolicyRevision, "BudgetPolicyRevision"),
    }

    def __init__(self, connect_factory: ConnectFactory | None = None, *, budget_store=None) -> None:
        self._connect_factory = connect_factory or db_connect
        self._budget_store = budget_store or AipBudgetAuthorityStore(connect_factory or db_connect)

    def publish_quota(self, scope, actor, key, item, *, expected_version=0):
        return self._publish("quota", scope, actor, key, item, expected_version)

    def publish_budget(self, scope, actor, key, item, *, expected_version=0):
        return self._publish("budget", scope, actor, key, item, expected_version)

    def get_quota(self, scope, policy_id, revision=None):
        return self._get("quota", scope, policy_id, revision)

    def get_budget(self, scope, policy_id, revision=None):
        return self._get("budget", scope, policy_id, revision)

    def get_quota_head(self, scope: TenantScope, policy_id: str):
        return self._get_head("quota", scope, policy_id)

    def get_budget_head(self, scope: TenantScope, policy_id: str):
        return self._get_head("budget", scope, policy_id)

    def require_exact_active(self, scope: TenantScope, ref: VersionedAssetRef, *, now: datetime | None = None):
        kind = {"QuotaPolicyRevision": "quota", "BudgetPolicyRevision": "budget"}.get(ref.asset_type)
        if kind is None:
            raise ModelGovernancePolicyDependencyBlocked("unsupported model governance policy ref")
        try:
            item = self._get(kind, scope, ref.asset_id, ref.revision)
        except ModelGovernancePolicyNotFound:
            raise ModelGovernancePolicyDependencyBlocked("exact model governance policy is unavailable") from None
        instant = now or datetime.now(UTC)
        if item.content_hash != ref.content_hash:
            raise ModelGovernancePolicyDependencyBlocked("model governance policy exact ref drifted")
        if item.lifecycle is not ModelGovernancePolicyLifecycle.ACTIVE:
            raise ModelGovernancePolicyDependencyBlocked("model governance policy is not active")
        if not (item.effective_from <= instant < item.effective_until):
            raise ModelGovernancePolicyDependencyBlocked("model governance policy is outside effective window")
        if isinstance(item, BudgetPolicyRevision):
            self._require_budget_revision(scope, item, now=instant)
        return item

    def require_model_dependencies(self, scope: TenantScope, model: Any) -> None:
        self.require_exact_active(scope, model.quota_policy_ref)
        self.require_exact_active(scope, model.budget_policy_ref)

    def require_runtime_policy_dependencies(self, scope: TenantScope, policy: Any) -> None:
        self.require_exact_active(scope, policy.quota_policy_ref)
        self.require_exact_active(scope, policy.budget_policy_ref)

    def _require_budget_revision(self, scope: TenantScope, item: BudgetPolicyRevisionCreate | BudgetPolicyRevision, *, now: datetime | None = None) -> None:
        ref = item.budget_revision_ref
        try:
            budget = self._budget_store.get(scope, ref.asset_id, ref.revision)
        except BudgetNotFound:
            raise ModelGovernancePolicyDependencyBlocked("exact BudgetRevision is unavailable") from None
        instant = now or datetime.now(UTC)
        if budget.content_hash != ref.content_hash:
            raise ModelGovernancePolicyDependencyBlocked("BudgetRevision exact ref drifted")
        if budget.lifecycle is not BudgetLifecycle.ACTIVE:
            raise ModelGovernancePolicyDependencyBlocked("BudgetRevision is not active")
        if not (budget.effective_from <= instant < budget.effective_until):
            raise ModelGovernancePolicyDependencyBlocked("BudgetRevision is outside effective window")
        if not budget.hard_stop or budget.unknown_usage_behavior != "block":
            raise ModelGovernancePolicyDependencyBlocked("BudgetRevision is outside approved fail-closed boundary")
        if item.currency != budget.currency:
            raise ModelGovernancePolicyDependencyBlocked("BudgetPolicy currency does not match BudgetRevision")
        if item.effective_from < budget.effective_from or item.effective_until > budget.effective_until:
            raise ModelGovernancePolicyDependencyBlocked("BudgetPolicy window exceeds BudgetRevision")

    def _publish(self, kind: str, scope: TenantScope, actor: str, key: str, item: CreateT, expected_version: int):
        request_hash = canonical_hash({"expectedVersion": expected_version, "revision": item.model_dump(mode="json", by_alias=True)})
        operation = f"model_governance_policy.{kind}.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay:
                return self._get(kind, scope, replay["resourceId"], int(replay["revision"]), conn=conn)
            if kind == "budget":
                self._require_budget_revision(scope, item)
            head = conn.execute(
                "SELECT current_revision,version FROM aip_model_governance_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s FOR UPDATE",
                (*scope.key, kind, item.policy_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise ModelGovernancePolicyConflict("stale model governance policy head version")
            next_revision = int(head["current_revision"]) + 1 if head else 1
            if item.revision != next_revision:
                raise ModelGovernancePolicyConflict("revision is not the next model governance policy revision")
            result = materialize_policy(scope, actor, item)
            if head:
                conn.execute(
                    "UPDATE aip_model_governance_policy_head SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s",
                    (result.revision, *scope.key, kind, result.policy_id),
                )
            else:
                conn.execute(
                    "INSERT INTO aip_model_governance_policy_head(org_id,project_id,policy_kind,policy_id,current_revision,version) VALUES(%s,%s,%s,%s,%s,1)",
                    (*scope.key, kind, result.policy_id, result.revision),
                )
            conn.execute(
                """INSERT INTO aip_model_governance_policy_revision(
                org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
                effective_from,effective_until,payload,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (*scope.key, kind, result.policy_id, result.revision, result.content_hash,
                 result.lifecycle.value, result.effective_from, result.effective_until,
                 self._json(result.model_dump(mode="json", by_alias=True)), actor, result.created_at),
            )
            result_ref = {"resourceType": self._SPECS[kind][2], "resourceId": result.policy_id,
                          "revision": result.revision, "contentHash": result.content_hash}
            conn.execute(
                """INSERT INTO aip_model_governance_policy_receipt(
                org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (*scope.key, f"aip10p-{uuid.uuid4().hex[:20]}", operation, key, request_hash,
                 self._json(result_ref), actor),
            )
            conn.commit()
            return self._get(kind, scope, result.policy_id, result.revision, conn=conn)

    def _get(self, kind: str, scope: TenantScope, policy_id: str, revision: int | None = None, *, conn=None):
        model = self._SPECS[kind][1]

        def read(connection):
            target = revision
            if target is None:
                head = connection.execute(
                    "SELECT current_revision FROM aip_model_governance_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s",
                    (*scope.key, kind, policy_id),
                ).fetchone()
                if not head:
                    raise ModelGovernancePolicyNotFound("model governance policy not found")
                target = int(head["current_revision"])
            row = connection.execute(
                "SELECT payload FROM aip_model_governance_policy_revision WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s AND revision=%s",
                (*scope.key, kind, policy_id, target),
            ).fetchone()
            if not row:
                raise ModelGovernancePolicyNotFound("model governance policy revision not found")
            return model.model_validate(self._load(row["payload"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def _get_head(self, kind: str, scope: TenantScope, policy_id: str):
        with self._connect_factory(scope) as connection:
            row = connection.execute(
                "SELECT current_revision,version FROM aip_model_governance_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s",
                (*scope.key, kind, policy_id),
            ).fetchone()
            if not row:
                raise ModelGovernancePolicyNotFound(
                    "model governance policy not found"
                )
            item = self._get(
                kind,
                scope,
                policy_id,
                int(row["current_revision"]),
                conn=connection,
            )
            return item, int(row["version"])

    def _replay(self, conn, scope, operation, key, request_hash):
        row = conn.execute(
            "SELECT request_hash,result_ref FROM aip_model_governance_policy_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise ModelGovernancePolicyIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value
