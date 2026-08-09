"""Tenant-scoped PostgreSQL DLQ with frozen error classification and receipts."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from aos_api.db import connect
from aos_api.ecom_core_models import EcomConsistencyError
from aos_api.tenant_scope import TenantScope


CanonicalErrorCode = Literal[
    "SOURCE_CONNECTION_ERROR", "STORE_CONFLICT", "VALIDATION_ERROR"
]

_ECOM_ERROR_CODE_MAP = {
    "IDEMPOTENCY_CONFLICT": "STORE_CONFLICT",
    "CONCURRENT_WRITE_CONFLICT": "STORE_CONFLICT",
    "SOURCE_VERSION_CONFLICT": "STORE_CONFLICT",
    "DANGLING_LINK": "VALIDATION_ERROR",
    "CHECKPOINT_CAS_CONFLICT": "STORE_CONFLICT",
    "CHECKPOINT_BOUNDARY_INVALID": "VALIDATION_ERROR",
    "CHECKPOINT_REGRESSION": "VALIDATION_ERROR",
}
SOURCE_ERROR_CODES = frozenset(
    {
        *_ECOM_ERROR_CODE_MAP,
        "CONNECTION_ERROR",
        "TIMEOUT",
        "OS_ERROR",
        "SQL_INTEGRITY_ERROR",
        "VALUE_ERROR",
        "KEY_ERROR",
        "TYPE_ERROR",
        "UNCLASSIFIED_EXCEPTION",
    }
)
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "body",
        "credential",
        "credentials",
        "input",
        "input_data",
        "password",
        "payload",
        "sample_input",
        "secret",
        "token",
    }
)
_PII_PATTERNS = (
    re.compile(r"\d{15,18}"),
    re.compile(r"62\d{14,17}"),
    re.compile(r"1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}"),
    re.compile(r"\S+@\S+\.\S+"),
    re.compile(r"openid[_\w-]+", re.IGNORECASE),
)
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(password|token|secret|authorization)\s*[:=]\s*[^\s,;]+"
)


@dataclass(frozen=True, slots=True)
class ErrorClassification:
    error_code: CanonicalErrorCode
    source_error_code: str | None


class DlqIdempotencyConflict(RuntimeError):
    pass


def classify_pipeline_error(exc: Exception) -> ErrorClassification:
    if isinstance(exc, EcomConsistencyError):
        source_code = (
            exc.code if exc.code in _ECOM_ERROR_CODE_MAP else "UNCLASSIFIED_EXCEPTION"
        )
        return ErrorClassification(
            _ECOM_ERROR_CODE_MAP.get(exc.code, "VALIDATION_ERROR"), source_code
        )
    if isinstance(exc, TimeoutError):
        return ErrorClassification("SOURCE_CONNECTION_ERROR", "TIMEOUT")
    if isinstance(exc, ConnectionError):
        return ErrorClassification("SOURCE_CONNECTION_ERROR", "CONNECTION_ERROR")
    if isinstance(exc, OSError):
        return ErrorClassification("SOURCE_CONNECTION_ERROR", "OS_ERROR")
    if exc.__class__.__name__ == "IntegrityError":
        return ErrorClassification("STORE_CONFLICT", "SQL_INTEGRITY_ERROR")
    if isinstance(exc, ValueError):
        return ErrorClassification("VALIDATION_ERROR", "VALUE_ERROR")
    if isinstance(exc, KeyError):
        return ErrorClassification("VALIDATION_ERROR", "KEY_ERROR")
    if isinstance(exc, TypeError):
        return ErrorClassification("VALIDATION_ERROR", "TYPE_ERROR")
    return ErrorClassification("VALIDATION_ERROR", "UNCLASSIFIED_EXCEPTION")


def _sanitize_text(value: str) -> str:
    sanitized = _CREDENTIAL_PATTERN.sub(lambda m: f"{m.group(1)}=***", value)
    for pattern in _PII_PATTERNS:
        sanitized = pattern.sub("***", sanitized)
    return sanitized[:2000]


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        return {
            str(key): sanitize_metadata(item)
            for key, item in value.items()
            if str(key).strip().lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_metadata(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize_text(str(value))


def _hash_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["dlq_id"]),
        "pipelineId": row["pipeline_id"],
        "errorCode": row["error_code"],
        "sourceErrorCode": row["source_error_code"],
        "reason": row["reason"],
        "metadata": row["metadata"],
        "payloadHash": row["payload_hash"],
        "status": row["status"],
        "retry_count": row["retry_count"],
        "max_retry": row["max_retry"],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
        "orgId": row["org_id"],
        "projectId": row["workspace_id"],
    }


def record_failure(
    *,
    pipeline: Any,
    scope: TenantScope,
    exc: Exception,
    run_id: str,
    stage_id: str,
    attempt_no: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classify_pipeline_error(exc)
    pipeline_id = str(getattr(pipeline, "id", "unknown") or "unknown")
    reason = _sanitize_text(f"{type(exc).__name__}: {exc}")
    safe_metadata = sanitize_metadata(metadata or {})
    payload = {
        "pipelineId": pipeline_id,
        "errorCode": classification.error_code,
        "sourceErrorCode": classification.source_error_code,
        "reason": reason,
        "metadata": safe_metadata,
    }
    payload_hash = _hash_json(payload)
    idem_material = "\x1f".join(
        (
            run_id,
            pipeline_id,
            stage_id,
            str(attempt_no),
            classification.error_code,
        )
    )
    idempotency_key = hashlib.sha256(idem_material.encode("utf-8")).hexdigest()
    dlq_id = uuid.uuid5(uuid.NAMESPACE_URL, f"aos-dlq:{scope.org_id}:{scope.project_id}:{idempotency_key}")

    with connect(scope) as conn:
        existing = conn.execute(
            "SELECT * FROM ecom_dlq WHERE org_id=%s AND workspace_id=%s "
            "AND idempotency_key=%s FOR UPDATE",
            (*scope.key, idempotency_key),
        ).fetchone()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise DlqIdempotencyConflict(
                    "DLQ idempotency key was reused with a different request"
                )
            return _as_item(existing)
        row = conn.execute(
            """
            INSERT INTO ecom_dlq (
              org_id,workspace_id,dlq_id,idempotency_key,pipeline_id,
              error_code,source_error_code,reason,metadata,payload_hash
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            RETURNING *
            """,
            (
                *scope.key,
                dlq_id,
                idempotency_key,
                pipeline_id,
                classification.error_code,
                classification.source_error_code,
                reason,
                json.dumps(safe_metadata, ensure_ascii=False),
                payload_hash,
            ),
        ).fetchone()
        return _as_item(row)


def list_failures(scope: TenantScope) -> list[dict[str, Any]]:
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT * FROM ecom_dlq WHERE org_id=%s AND workspace_id=%s "
            "ORDER BY created_at, dlq_id",
            scope.key,
        ).fetchall()
    return [_as_item(row) for row in rows]


def retry_failure(
    *,
    scope: TenantScope,
    dlq_id: str,
    retry_idempotency_key: str,
    actor: str,
) -> dict[str, Any]:
    request_hash = _hash_json(
        {"dlqId": dlq_id, "retryIdempotencyKey": retry_idempotency_key, "actor": actor}
    )
    with connect(scope) as conn:
        receipt = conn.execute(
            "SELECT request_hash FROM ecom_dlq_retry_receipt "
            "WHERE org_id=%s AND workspace_id=%s AND dlq_id=%s "
            "AND retry_idempotency_key=%s",
            (*scope.key, dlq_id, retry_idempotency_key),
        ).fetchone()
        if receipt:
            if receipt["request_hash"] != request_hash:
                raise DlqIdempotencyConflict(
                    "retry idempotency key was reused with a different request"
                )
            row = conn.execute(
                "SELECT * FROM ecom_dlq WHERE org_id=%s AND workspace_id=%s AND dlq_id=%s",
                (*scope.key, dlq_id),
            ).fetchone()
            if row is None:
                raise KeyError("DLQ entry not found")
            return _as_item(row)

        row = conn.execute(
            "SELECT * FROM ecom_dlq WHERE org_id=%s AND workspace_id=%s "
            "AND dlq_id=%s FOR UPDATE",
            (*scope.key, dlq_id),
        ).fetchone()
        if row is None:
            raise KeyError("DLQ entry not found")
        if row["retry_count"] >= row["max_retry"]:
            raise RuntimeError("DLQ retry limit reached")
        next_attempt = int(row["retry_count"]) + 1
        now = datetime.now().astimezone()
        updated = conn.execute(
            "UPDATE ecom_dlq SET status='retried',retry_count=%s,last_retry_at=%s,"
            "updated_at=%s WHERE org_id=%s AND workspace_id=%s AND dlq_id=%s RETURNING *",
            (next_attempt, now, now, *scope.key, dlq_id),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO ecom_dlq_retry_receipt (
              org_id,workspace_id,dlq_id,retry_idempotency_key,request_hash,
              attempt_no,accepted_from_status,actor
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                *scope.key,
                dlq_id,
                retry_idempotency_key,
                request_hash,
                next_attempt,
                row["status"],
                actor,
            ),
        )
        conn.execute(
            "INSERT INTO ecom_dlq_retry_event "
            "(org_id,workspace_id,event_id,dlq_id,event_type,payload) "
            "VALUES (%s,%s,%s,%s,'retry_succeeded',%s::jsonb)",
            (*scope.key, uuid.uuid4(), dlq_id, json.dumps({"attemptNo": next_attempt})),
        )
        return _as_item(updated)
