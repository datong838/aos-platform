"""Internal tenant-safe authority Store for W3-12A operation cases."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.db import connect as db_connect
from aos_api.ecommerce_operation_case_contracts import (
    AggregationPolicyRevision,
    ExactAuthorityRevisionRef,
    OperationCaseRevision,
)
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class OperationAuthorityStoreError(RuntimeError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_ERROR"


class OperationAuthorityConflict(OperationAuthorityStoreError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_VERSION_CONFLICT"


class OperationAuthorityIdempotencyConflict(OperationAuthorityStoreError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_IDEMPOTENCY_CONFLICT"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class OperationAuthorityStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish_policy(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: AggregationPolicyRevision,
        *,
        expected_version: int,
    ) -> ExactAuthorityRevisionRef:
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.actor)
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(
            {"expectedVersion": expected_version, "revision": payload}
        )
        operation = "operation_aggregation_policy.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ExactAuthorityRevisionRef.model_validate(replay)
            head = conn.execute(
                "SELECT current_revision,version FROM "
                "ecommerce_operation_aggregation_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s FOR UPDATE",
                (*scope.key, item.policy_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise OperationAuthorityConflict("stale aggregation policy version")
            if item.revision != version + 1 or item.version != version + 1:
                raise OperationAuthorityConflict("policy revision/version must advance once")
            if head:
                conn.execute(
                    "UPDATE ecommerce_operation_aggregation_policy_head "
                    "SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                    (item.revision, *scope.key, item.policy_id),
                )
            else:
                conn.execute(
                    "INSERT INTO ecommerce_operation_aggregation_policy_head"
                    "(org_id,project_id,policy_id,current_revision,version) "
                    "VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, item.policy_id, item.revision),
                )
            conn.execute(
                "INSERT INTO ecommerce_operation_aggregation_policy_revision"
                "(org_id,project_id,policy_id,revision,content_hash,payload,created_by,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (
                    *scope.key,
                    item.policy_id,
                    item.revision,
                    item.content_hash,
                    self._json(payload),
                    actor,
                    item.created_at,
                ),
            )
            result = self._ref(item.policy_id, item.revision, item.content_hash)
            self._receipt(conn, scope, operation, key, request_hash, result, actor)
            conn.commit()
            return result

    def create_case(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: OperationCaseRevision,
    ) -> ExactAuthorityRevisionRef:
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.actor)
        for member in item.member_refs:
            self._require_scope(scope, member.tenant.org_id, member.tenant.project_id)
        if item.revision != 1 or item.version != 1:
            raise OperationAuthorityConflict("new operation case must start at revision/version 1")
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        operation = "operation_case.create"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ExactAuthorityRevisionRef.model_validate(replay)
            policy = conn.execute(
                "SELECT current_revision FROM ecommerce_operation_aggregation_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                (*scope.key, item.aggregation_policy_ref.resource_id),
            ).fetchone()
            policy_revision = item.aggregation_policy_ref.revision
            if not policy or int(policy["current_revision"]) != policy_revision:
                raise OperationAuthorityConflict("exact aggregation policy is unavailable")
            head = conn.execute(
                "SELECT version FROM ecommerce_operation_case_head "
                "WHERE org_id=%s AND project_id=%s AND case_id=%s FOR UPDATE",
                (*scope.key, item.case_id),
            ).fetchone()
            if head:
                raise OperationAuthorityConflict("operation case already exists")
            conn.execute(
                "INSERT INTO ecommerce_operation_case_head"
                "(org_id,project_id,case_id,current_revision,version) VALUES(%s,%s,%s,1,1)",
                (*scope.key, item.case_id),
            )
            conn.execute(
                "INSERT INTO ecommerce_operation_case_revision"
                "(org_id,project_id,case_id,revision,content_hash,payload,created_by,created_at) "
                "VALUES(%s,%s,%s,1,%s,%s::jsonb,%s,%s)",
                (
                    *scope.key,
                    item.case_id,
                    item.content_hash,
                    self._json(payload),
                    actor,
                    item.created_at,
                ),
            )
            result = self._ref(item.case_id, 1, item.content_hash)
            self._receipt(conn, scope, operation, key, request_hash, result, actor)
            conn.commit()
            return result

    @staticmethod
    def _require_scope(scope: TenantScope, org_id: str, project_id: str) -> None:
        if (org_id, project_id) != scope.key:
            raise OperationAuthorityConflict("authority ref tenant does not match scope")

    @staticmethod
    def _require_actor(actor: str, revision_actor: str) -> None:
        if actor != revision_actor:
            raise OperationAuthorityConflict("revision actor does not match principal actor")

    @staticmethod
    def _ref(resource_id: str, revision: int, content_hash: str) -> ExactAuthorityRevisionRef:
        return ExactAuthorityRevisionRef(
            resource_id=resource_id,
            revision=revision,
            content_hash=content_hash,
        )

    def _replay(self, conn, scope, operation, key, request_hash):
        row = conn.execute(
            "SELECT request_hash,result_ref FROM ecommerce_operation_authority_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise OperationAuthorityIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None

    def _receipt(self, conn, scope, operation, key, request_hash, result, actor):
        conn.execute(
            "INSERT INTO ecommerce_operation_authority_receipt"
            "(org_id,project_id,receipt_id,operation,idempotency_key,"
            "request_hash,result_ref,created_by) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (
                *scope.key,
                f"op-receipt-{uuid.uuid4().hex[:20]}",
                operation,
                key,
                request_hash,
                self._json(result.model_dump(mode="json", by_alias=True)),
                actor,
            ),
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value


__all__ = [
    "OperationAuthorityConflict",
    "OperationAuthorityIdempotencyConflict",
    "OperationAuthorityStore",
]
