"""Pipeline failure bridge for the tenant-scoped PostgreSQL DLQ.

The authoritative contract lives in :mod:`aos_api.ec_dlq_store`.  This module
keeps the executor-facing API deliberately small and never replaces the
original pipeline exception when DLQ persistence itself fails.
"""

from __future__ import annotations

import logging
from typing import Any

from aos_api.ec_dlq_store import (
    classify_pipeline_error,
    record_failure,
    sanitize_metadata,
)

log = logging.getLogger(__name__)
MAX_RETRY = 3


def _sanitize_pii(text: str) -> str:
    """Compatibility facade used by the evidence scanner tests."""
    return str(sanitize_metadata(text))


def _sanitize_recursive(obj: Any) -> Any:
    """Compatibility facade; credentials and business payload fields fail closed."""
    return sanitize_metadata(obj)


def _summarize_exception(exc: Exception) -> str:
    return _sanitize_pii(f"{type(exc).__name__}: {exc}")


def handle_failure(
    pipeline: Any,
    scope: Any,
    exc: Exception,
    *,
    run_id: str,
    stage_id: str = "pipeline",
    attempt_no: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Persist one failure without swallowing or replacing the original error.

    ``run_id`` is mandatory: generating it in this handler would make retries
    non-idempotent and would break the reviewed DLQ evidence contract.
    """
    pipeline_id = str(getattr(pipeline, "id", "unknown") or "unknown")
    log.warning(
        "ec_pipeline_failed pipeline=%s run=%s scope=%s error=%s",
        pipeline_id,
        run_id,
        scope,
        type(exc).__name__,
    )
    try:
        item = record_failure(
            pipeline=pipeline,
            scope=scope,
            exc=exc,
            run_id=run_id,
            stage_id=stage_id,
            attempt_no=attempt_no,
            metadata=metadata,
        )
        log.info("ec_pipeline_dlq_pushed dlq_id=%s pipeline=%s", item["id"], pipeline_id)
        return item
    except Exception as dlq_exc:
        log.error(
            "ec_pipeline_dlq_push_failed pipeline=%s run=%s error=%s",
            pipeline_id,
            run_id,
            type(dlq_exc).__name__,
        )
        return None
