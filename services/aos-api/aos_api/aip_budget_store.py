"""PostgreSQL canonical authority for immutable tenant BudgetRevision records."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_budget_contracts import BudgetRevision, BudgetRevisionCreate
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BudgetStoreError(RuntimeError):
    code = "AIP_BUDGET_STORE_ERROR"


class BudgetNotFound(BudgetStoreError):
    code = "AIP_BUDGET_NOT_FOUND"


class BudgetConflict(BudgetStoreError):
    code = "AIP_BUDGET_VERSION_CONFLICT"


class BudgetIdempotencyConflict(BudgetStoreError):
    code = "AIP_BUDGET_IDEMPOTENCY_CONFLICT"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def materialize_revision(
    scope: TenantScope,
    actor: str,
    item: BudgetRevisionCreate,
    *,
    created_at: datetime | None = None,
) -> BudgetRevision:
    content = item.model_dump(mode="json", by_alias=True)
    return BudgetRevision.model_validate(
        {
            **content,
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "contentHash": canonical_hash(content),
            "createdBy": actor,
            "createdAt": created_at or datetime.now(UTC),
        }
    )


class AipBudgetAuthorityStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: BudgetRevisionCreate,
        *,
        expected_version: int = 0,
    ) -> BudgetRevision:
        request_hash = canonical_hash(
            {
                "expectedVersion": expected_version,
                "revision": item.model_dump(mode="json", by_alias=True),
            }
        )
        operation = "budget_revision.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay:
                return self.get(
                    scope,
                    replay["resourceId"],
                    int(replay["revision"]),
                    conn=conn,
                )
            head = conn.execute(
                "SELECT current_revision,version FROM aip_budget_head "
                "WHERE org_id=%s AND project_id=%s AND budget_id=%s FOR UPDATE",
                (*scope.key, item.budget_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise BudgetConflict("stale budget authority head version")
            next_revision = int(head["current_revision"]) + 1 if head else 1
            if item.revision != next_revision:
                raise BudgetConflict("revision is not the next budget authority revision")
            result = materialize_revision(scope, actor, item)
            if head:
                conn.execute(
                    "UPDATE aip_budget_head SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND budget_id=%s",
                    (result.revision, *scope.key, result.budget_id),
                )
            else:
                conn.execute(
                    "INSERT INTO aip_budget_head(org_id,project_id,budget_id,current_revision,version) "
                    "VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, result.budget_id, result.revision),
                )
            conn.execute(
                """INSERT INTO aip_budget_revision(
                org_id,project_id,budget_id,revision,content_hash,lifecycle,
                environment,currency,daily_limit_minor,monthly_limit_minor,
                alert_threshold_pct,hard_stop,unknown_usage_behavior,
                effective_from,effective_until,owner,over_budget_approver,
                payload,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    *scope.key,
                    result.budget_id,
                    result.revision,
                    result.content_hash,
                    result.lifecycle.value,
                    result.environment,
                    result.currency,
                    result.daily_limit_minor,
                    result.monthly_limit_minor,
                    result.alert_threshold_pct,
                    result.hard_stop,
                    result.unknown_usage_behavior,
                    result.effective_from,
                    result.effective_until,
                    result.owner,
                    result.over_budget_approver,
                    self._json(result.model_dump(mode="json", by_alias=True)),
                    actor,
                    result.created_at,
                ),
            )
            result_ref = {
                "resourceType": "BudgetRevision",
                "resourceId": result.budget_id,
                "revision": result.revision,
                "contentHash": result.content_hash,
            }
            conn.execute(
                """INSERT INTO aip_budget_receipt(
                org_id,project_id,receipt_id,operation,idempotency_key,
                request_hash,result_ref,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (
                    *scope.key,
                    f"aip10r-{uuid.uuid4().hex[:20]}",
                    operation,
                    key,
                    request_hash,
                    self._json(result_ref),
                    actor,
                ),
            )
            conn.commit()
            return self.get(scope, result.budget_id, result.revision, conn=conn)

    def get(
        self,
        scope: TenantScope,
        budget_id: str,
        revision: int | None = None,
        *,
        conn: Any | None = None,
    ) -> BudgetRevision:
        def read(connection: Any) -> BudgetRevision:
            target = revision
            if target is None:
                head = connection.execute(
                    "SELECT current_revision FROM aip_budget_head "
                    "WHERE org_id=%s AND project_id=%s AND budget_id=%s",
                    (*scope.key, budget_id),
                ).fetchone()
                if not head:
                    raise BudgetNotFound("budget not found")
                target = int(head["current_revision"])
            row = connection.execute(
                "SELECT payload FROM aip_budget_revision "
                "WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s",
                (*scope.key, budget_id, target),
            ).fetchone()
            if not row:
                raise BudgetNotFound("budget revision not found")
            return BudgetRevision.model_validate(self._load(row["payload"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def _replay(
        self,
        conn: Any,
        scope: TenantScope,
        operation: str,
        key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT request_hash,result_ref FROM aip_budget_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise BudgetIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value
