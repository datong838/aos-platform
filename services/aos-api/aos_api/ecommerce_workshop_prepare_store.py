"""PostgreSQL authority for Workshop preparation intent and result."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class PreparationStoreError(RuntimeError):
    code = "WORKSHOP_PREPARATION_STORE_ERROR"


class PreparationIdempotencyConflict(PreparationStoreError):
    code = "WORKSHOP_IDEMPOTENCY_CONFLICT"


class PreparationNotFound(PreparationStoreError):
    code = "WORKSHOP_PREPARATION_NOT_FOUND"


@dataclass(frozen=True)
class PreparationRecord:
    preparation_id: str
    module_id: str
    request_hash: str
    status: str
    result_body: dict[str, Any] | None


class EcommerceWorkshopPrepareStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def begin(
        self,
        scope: TenantScope,
        *,
        actor: str,
        module_id: str,
        idempotency_key: str,
        request_hash: str,
        request_body: dict[str, Any],
    ) -> PreparationRecord:
        try:
            with self._connect_factory(scope) as conn:
                current = conn.execute(
                    """SELECT intent.*, result.result_body
                       FROM aip_workshop_preparation_intent intent
                       LEFT JOIN aip_workshop_preparation_result result
                         ON result.org_id=intent.org_id
                        AND result.project_id=intent.project_id
                        AND result.preparation_id=intent.preparation_id
                        AND result.revision=1
                      WHERE intent.org_id=%s AND intent.project_id=%s
                        AND intent.operation='prepare' AND intent.idempotency_key=%s""",
                    (*scope.key, idempotency_key),
                ).fetchone()
                if current:
                    if current["request_hash"] != request_hash:
                        raise PreparationIdempotencyConflict(
                            "Idempotency-Key was already used for another prepare request"
                        )
                    return self._record(current)
                preparation_id = f"preparation-{uuid.uuid4().hex[:20]}"
                row = conn.execute(
                    """INSERT INTO aip_workshop_preparation_intent(
                       org_id,project_id,preparation_id,module_id,idempotency_key,
                       request_hash,request_body,status,created_by)
                       VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,'pending',%s)
                       RETURNING *""",
                    (
                        *scope.key,
                        preparation_id,
                        module_id,
                        idempotency_key,
                        request_hash,
                        self._json(request_body),
                        actor,
                    ),
                ).fetchone()
                conn.commit()
                return self._record(row)
        except PreparationStoreError:
            raise
        except Exception as exc:
            raise PreparationStoreError("preparation intent persistence failed") from exc

    def complete(
        self,
        scope: TenantScope,
        *,
        actor: str,
        preparation_id: str,
        request_hash: str,
        result_hash: str,
        result_body: dict[str, Any],
    ) -> PreparationRecord:
        try:
            with self._connect_factory(scope) as conn:
                intent = conn.execute(
                    """SELECT * FROM aip_workshop_preparation_intent
                       WHERE org_id=%s AND project_id=%s AND preparation_id=%s
                       FOR UPDATE""",
                    (*scope.key, preparation_id),
                ).fetchone()
                if not intent:
                    raise PreparationNotFound("preparation intent not found")
                if intent["request_hash"] != request_hash:
                    raise PreparationIdempotencyConflict("preparation request hash drifted")
                existing = conn.execute(
                    """SELECT result_body FROM aip_workshop_preparation_result
                       WHERE org_id=%s AND project_id=%s AND preparation_id=%s AND revision=1""",
                    (*scope.key, preparation_id),
                ).fetchone()
                if existing:
                    return PreparationRecord(
                        preparation_id=preparation_id,
                        module_id=intent["module_id"],
                        request_hash=request_hash,
                        status="complete",
                        result_body=self._object(existing["result_body"]),
                    )
                conn.execute(
                    """INSERT INTO aip_workshop_preparation_result(
                       org_id,project_id,preparation_id,revision,request_hash,
                       result_hash,result_body,created_by)
                       VALUES(%s,%s,%s,1,%s,%s,%s::jsonb,%s)""",
                    (
                        *scope.key,
                        preparation_id,
                        request_hash,
                        result_hash,
                        self._json(result_body),
                        actor,
                    ),
                )
                conn.execute(
                    """UPDATE aip_workshop_preparation_intent
                       SET status='complete',updated_at=NOW()
                       WHERE org_id=%s AND project_id=%s AND preparation_id=%s""",
                    (*scope.key, preparation_id),
                )
                conn.commit()
                return PreparationRecord(
                    preparation_id=preparation_id,
                    module_id=intent["module_id"],
                    request_hash=request_hash,
                    status="complete",
                    result_body=result_body,
                )
        except PreparationStoreError:
            raise
        except Exception as exc:
            raise PreparationStoreError("preparation result persistence failed") from exc

    def get(self, scope: TenantScope, preparation_id: str) -> PreparationRecord:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT intent.*, result.result_body
                       FROM aip_workshop_preparation_intent intent
                       LEFT JOIN aip_workshop_preparation_result result
                         ON result.org_id=intent.org_id
                        AND result.project_id=intent.project_id
                        AND result.preparation_id=intent.preparation_id
                        AND result.revision=1
                      WHERE intent.org_id=%s AND intent.project_id=%s
                        AND intent.preparation_id=%s""",
                    (*scope.key, preparation_id),
                ).fetchone()
            if row is None:
                raise PreparationNotFound("preparation not found")
            return self._record(row)
        except PreparationStoreError:
            raise
        except Exception as exc:
            raise PreparationStoreError("preparation read failed") from exc

    @staticmethod
    def _record(row: Any) -> PreparationRecord:
        result = row.get("result_body") if hasattr(row, "get") else None
        return PreparationRecord(
            preparation_id=row["preparation_id"],
            module_id=row["module_id"],
            request_hash=row["request_hash"],
            status=row["status"],
            result_body=EcommerceWorkshopPrepareStore._object(result) if result else None,
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _object(value: Any) -> dict[str, Any]:
        parsed = json.loads(value) if isinstance(value, str) else value
        if not isinstance(parsed, dict):
            raise PreparationStoreError("preparation result is not an object")
        return parsed
