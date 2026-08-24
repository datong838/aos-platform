"""Internal tenant-safe authority Store for W3-12A operation cases."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import psycopg

from aos_api.db import connect as db_connect
from aos_api.ecommerce_operation_case_contracts import (
    AggregationPolicyRevision,
    AutomationKillDecisionRevision,
    CaseMembershipDecisionRevision,
    ExactAuthorityRevisionRef,
    OperationCaseEvent,
    OperationCaseRevision,
    OperationAuthorityReceipt,
    OperationEventClassificationDecisionRevision,
    SlaClockDecision,
    SlaPolicyRevision,
)
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class OperationAuthorityStoreError(RuntimeError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_ERROR"


class OperationAuthorityConflict(OperationAuthorityStoreError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_VERSION_CONFLICT"


class OperationAuthorityIdempotencyConflict(OperationAuthorityStoreError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_IDEMPOTENCY_CONFLICT"


class OperationAuthorityReadError(OperationAuthorityStoreError):
    code = "ECOMMERCE_OPERATION_AUTHORITY_READ_FAILED"


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

    def list_cases(
        self,
        scope: TenantScope,
        *,
        limit: int = 50,
    ) -> list[OperationCaseRevision]:
        if not 1 <= limit <= 50:
            raise ValueError("operation case limit must be between 1 and 50")
        try:
            with self._connect_factory(scope) as conn:
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                rows = conn.execute(
                    "SELECT revision.payload FROM ecommerce_operation_case_head head "
                    "JOIN ecommerce_operation_case_revision revision "
                    "ON revision.org_id=head.org_id AND revision.project_id=head.project_id "
                    "AND revision.case_id=head.case_id "
                    "AND revision.revision=head.current_revision "
                    "WHERE head.org_id=%s AND head.project_id=%s "
                    "ORDER BY revision.created_at DESC,revision.case_id LIMIT %s",
                    (*scope.key, limit),
                ).fetchall()
                return [
                    OperationCaseRevision.model_validate(self._load(row["payload"]))
                    for row in rows
                ]
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise OperationAuthorityReadError(
                "canonical operation case read failed closed"
            ) from exc

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

    def get_receipt(
        self,
        scope: TenantScope,
        *,
        operation: str,
        idempotency_key: str,
    ) -> OperationAuthorityReceipt:
        """Read the exact immutable Receipt created by a successful command."""
        try:
            with self._connect_factory(scope) as conn:
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                row = conn.execute(
                    "SELECT receipt_id,operation,idempotency_key,request_hash,"
                    "result_ref,created_by,created_at "
                    "FROM ecommerce_operation_authority_receipt "
                    "WHERE org_id=%s AND project_id=%s AND operation=%s "
                    "AND idempotency_key=%s",
                    (*scope.key, operation, idempotency_key),
                ).fetchone()
            if row is None:
                raise OperationAuthorityReadError(
                    "operation authority Receipt is unavailable"
                )
            return OperationAuthorityReceipt(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                receipt_id=row["receipt_id"],
                operation=row["operation"],
                idempotency_key=row["idempotency_key"],
                request_hash=row["request_hash"],
                result_ref=self._load(row["result_ref"]),
                created_by=row["created_by"],
                created_at=row["created_at"],
            )
        except OperationAuthorityReadError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise OperationAuthorityReadError(
                "operation authority Receipt read failed closed"
            ) from exc

    def publish_sla_policy(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: SlaPolicyRevision,
        *,
        expected_version: int,
    ) -> ExactAuthorityRevisionRef:
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.actor)
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(
            {"expectedVersion": expected_version, "revision": payload}
        )
        operation = "operation_sla_policy.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ExactAuthorityRevisionRef.model_validate(replay)
            head = conn.execute(
                "SELECT current_revision,version FROM ecommerce_operation_sla_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s FOR UPDATE",
                (*scope.key, item.policy_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise OperationAuthorityConflict("stale SLA policy version")
            if item.revision != version + 1 or item.version != version + 1:
                raise OperationAuthorityConflict("SLA policy revision/version must advance once")
            if head:
                conn.execute(
                    "UPDATE ecommerce_operation_sla_policy_head "
                    "SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                    (item.revision, *scope.key, item.policy_id),
                )
            else:
                conn.execute(
                    "INSERT INTO ecommerce_operation_sla_policy_head"
                    "(org_id,project_id,policy_id,current_revision,version) "
                    "VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, item.policy_id, item.revision),
                )
            conn.execute(
                "INSERT INTO ecommerce_operation_sla_policy_revision"
                "(org_id,project_id,policy_id,revision,content_hash,payload,created_by,"
                "created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
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

    def append_classification(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: OperationEventClassificationDecisionRevision,
    ) -> ExactAuthorityRevisionRef:
        self._require_scope(
            scope, item.original_ref.tenant.org_id, item.original_ref.tenant.project_id
        )
        return self._append_decision(
            scope,
            actor,
            key,
            item,
            table="ecommerce_operation_classification_decision_revision",
            identity=item.decision_id,
            operation="operation_classification.append",
        )

    def append_membership(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: CaseMembershipDecisionRevision,
    ) -> ExactAuthorityRevisionRef:
        for original in item.moved_originals:
            self._require_scope(
                scope, original.tenant.org_id, original.tenant.project_id
            )
        return self._append_decision(
            scope,
            actor,
            key,
            item,
            table="ecommerce_operation_membership_decision_revision",
            identity=item.decision_id,
            operation="operation_membership.append",
        )

    def append_sla_clock(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: SlaClockDecision,
    ) -> ExactAuthorityRevisionRef:
        return self._append_decision(
            scope,
            actor,
            key,
            item,
            table="ecommerce_operation_sla_clock_decision",
            identity=item.decision_id,
            operation="operation_sla_clock.append",
        )

    def append_kill(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: AutomationKillDecisionRevision,
    ) -> ExactAuthorityRevisionRef:
        return self._append_decision(
            scope,
            actor,
            key,
            item,
            table="ecommerce_operation_kill_decision_revision",
            identity=item.decision_id,
            operation="operation_kill.append",
        )

    def append_case_event(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: OperationCaseEvent,
    ) -> ExactAuthorityRevisionRef:
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.actor)
        if item.original_ref is not None:
            self._require_scope(
                scope,
                item.original_ref.tenant.org_id,
                item.original_ref.tenant.project_id,
            )
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        operation = "operation_case_event.append"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ExactAuthorityRevisionRef.model_validate(replay)
            conn.execute(
                "INSERT INTO ecommerce_operation_case_event"
                "(org_id,project_id,event_id,revision,content_hash,payload,created_by,"
                "created_at,case_id,sequence) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
                (
                    *scope.key,
                    item.event_id,
                    item.revision,
                    item.content_hash,
                    self._json(payload),
                    actor,
                    item.created_at,
                    item.case_ref.resource_id,
                    item.sequence,
                ),
            )
            result = self._ref(item.event_id, item.revision, item.content_hash)
            self._receipt(conn, scope, operation, key, request_hash, result, actor)
            conn.commit()
            return result

    def _append_decision(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: Any,
        *,
        table: str,
        identity: str,
        operation: str,
    ) -> ExactAuthorityRevisionRef:
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        self._require_actor(actor, item.actor)
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay is not None:
                return ExactAuthorityRevisionRef.model_validate(replay)
            conn.execute(
                f"INSERT INTO {table}"
                "(org_id,project_id,decision_id,revision,content_hash,payload,"
                "created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (
                    *scope.key,
                    identity,
                    item.revision,
                    item.content_hash,
                    self._json(payload),
                    actor,
                    item.created_at,
                ),
            )
            result = self._ref(identity, item.revision, item.content_hash)
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
    "OperationAuthorityReadError",
    "OperationAuthorityStore",
]
