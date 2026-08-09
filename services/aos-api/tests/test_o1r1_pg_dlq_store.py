from __future__ import annotations

from types import SimpleNamespace

import pytest

from aos_api.ecom_core_models import EcomConsistencyError
from aos_api.ec_dlq_store import (
    DlqIdempotencyConflict,
    classify_pipeline_error,
    list_failures,
    record_failure,
    retry_failure,
    sanitize_metadata,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("org-org", "other-project")


def test_classifier_uses_only_frozen_codes() -> None:
    conflict = classify_pipeline_error(
        EcomConsistencyError("IDEMPOTENCY_CONFLICT", "duplicate")
    )
    assert conflict.error_code == "STORE_CONFLICT"
    assert conflict.source_error_code == "IDEMPOTENCY_CONFLICT"
    unknown = classify_pipeline_error(RuntimeError("boom"))
    assert unknown.error_code == "VALIDATION_ERROR"
    assert unknown.source_error_code == "UNCLASSIFIED_EXCEPTION"


def test_record_failure_is_persistent_sanitized_and_tenant_scoped() -> None:
    item = record_failure(
        pipeline=SimpleNamespace(id="pipe-pg-dlq"),
        scope=SCOPE,
        exc=RuntimeError("phone 13800138000 password=secret"),
        run_id="run-pg-dlq-1",
        stage_id="source",
        attempt_no=1,
        metadata={"nested": {"email": "a@b.com", "password": "secret"}},
    )
    assert item["errorCode"] == "VALIDATION_ERROR"
    assert item["sourceErrorCode"] == "UNCLASSIFIED_EXCEPTION"
    assert "13800138000" not in item["reason"]
    assert "secret" not in str(item)
    assert len(item["payloadHash"]) == 64
    assert item["id"] in [row["id"] for row in list_failures(SCOPE)]
    assert item["id"] not in [row["id"] for row in list_failures(OTHER_SCOPE)]


def test_recursive_sanitizer_redacts_sensitive_identity_keys_and_nested_values() -> None:
    sanitized = sanitize_metadata(
        {
            "phone": "13800000000",
            "openid": "oX1234567890abcdef",
            "nickname_test": "真实昵称",
            "meta": {"mobile": "138-0000-0000"},
            "tags": ["110101199001011234"],
            "safe": "保留字段",
        }
    )
    serialized = str(sanitized)
    assert sanitized["safe"] == "保留字段"
    assert "13800000000" not in serialized
    assert "138-0000-0000" not in serialized
    assert "110101199001011234" not in serialized
    assert "oX1234567890abcdef" not in serialized
    assert "真实昵称" not in serialized


def test_sanitizer_does_not_redact_audit_tenant_identifier() -> None:
    assert sanitize_metadata("org-d5e-a-01234567") == "org-d5e-a-01234567"


def test_record_failure_replays_same_request_and_rejects_changed_request() -> None:
    kwargs = dict(
        pipeline=SimpleNamespace(id="pipe-idem"),
        scope=SCOPE,
        exc=ValueError("bad row"),
        run_id="run-idem",
        stage_id="normalize",
        attempt_no=1,
    )
    first = record_failure(**kwargs)
    replay = record_failure(**kwargs)
    assert replay == first
    with pytest.raises(DlqIdempotencyConflict):
        record_failure(**{**kwargs, "metadata": {"changed": True}})


def test_retry_failure_writes_immutable_receipt() -> None:
    item = record_failure(
        pipeline=SimpleNamespace(id="pipe-retry"),
        scope=SCOPE,
        exc=ConnectionError("source unavailable"),
        run_id="run-retry",
        stage_id="source",
        attempt_no=1,
    )
    retried = retry_failure(
        scope=SCOPE,
        dlq_id=item["id"],
        retry_idempotency_key="retry-1",
        actor="user:dev",
    )
    assert retried["status"] == "retried"
    assert retried["retry_count"] == 1
    assert retry_failure(
        scope=SCOPE,
        dlq_id=item["id"],
        retry_idempotency_key="retry-1",
        actor="user:dev",
    ) == retried
