"""G6 PostgreSQL DLQ bridge tests."""

from __future__ import annotations

import logging

import pytest

from aos_api.ec_dlq_handler import handle_failure
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


class _FakePipeline:
    def __init__(self, pid: str = "pipe-1"):
        self.id = pid


def _record(pid: str, exc: Exception, run_id: str):
    item = handle_failure(_FakePipeline(pid), TEST_SCOPE, exc, run_id=run_id)
    assert item is not None
    return item


def test_handle_failure_persists_frozen_contract() -> None:
    item = _record("pipe-contract", RuntimeError("boom"), "run-contract")
    assert item["pipelineId"] == "pipe-contract"
    assert item["errorCode"] == "VALIDATION_ERROR"
    assert item["sourceErrorCode"] == "UNCLASSIFIED_EXCEPTION"
    assert item["status"] == "open"
    assert item["retry_count"] == 0
    assert item["max_retry"] == 3
    assert item["createdAt"]


def test_dlq_entry_does_not_contain_pii_or_credentials() -> None:
    item = _record(
        "pipe-pii",
        RuntimeError("phone 13800138000 password=secret email=a@b.com"),
        "run-pii",
    )
    serialized = str(item)
    assert "13800138000" not in serialized
    assert "a@b.com" not in serialized
    assert "secret" not in serialized
    for forbidden in ("input", "input_data", "payload", "credentials", "body"):
        assert forbidden not in item


def test_handle_failure_does_not_replace_original_exception() -> None:
    original = RuntimeError("original failure")
    try:
        raise original
    except Exception as exc:
        assert handle_failure(
            _FakePipeline("pipe-original"),
            TEST_SCOPE,
            exc,
            run_id="run-original",
        ) is not None
        assert exc is original


def test_handler_logs_warning() -> None:
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("aos_api.ec_dlq_handler")
    logger.disabled = False
    capture = _Capture()
    logger.addHandler(capture)
    try:
        _record("pipe-log", RuntimeError("boom"), "run-log")
    finally:
        logger.removeHandler(capture)
    assert any("ec_pipeline_failed" in record.getMessage() for record in records)


def test_ec_live_executor_reraises_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    from aos_api import ec_live_executor as mod

    monkeypatch.setattr(
        mod,
        "fetch_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("source fetch failed")),
    )
    with pytest.raises(RuntimeError, match="source fetch failed"):
        mod.ec_live_executor(
            pipeline=_FakePipeline("pipe-ec"),
            nodes=[],
            node_id=None,
            sample_input={},
            execution_kind="schedule",
            cancel_event=None,
            deadline=0,
            scope=TEST_SCOPE,
            run_id="run-ec-live",
        )


def test_ec_live_executor_without_run_id_fails_closed_without_masking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_api import ec_live_executor as mod

    monkeypatch.setattr(
        mod,
        "fetch_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("original")),
    )
    with pytest.raises(ValueError, match="original"):
        mod.ec_live_executor(
            pipeline=_FakePipeline("pipe-no-run"), nodes=[], node_id=None,
            sample_input={}, execution_kind="direct", cancel_event=None,
            deadline=0, scope=TEST_SCOPE,
        )
