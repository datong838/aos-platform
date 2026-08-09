"""Persistent DLQ PII and credential zero-leak checks."""

from __future__ import annotations

import re

import pytest

from aos_api.ec_dlq_handler import _sanitize_pii, handle_failure
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
_PII_REGEXES = (
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"\d{15,18}"),
    re.compile(r"62\d{14,17}"),
    re.compile(r"\S+@\S+\.\S+"),
)


@pytest.mark.parametrize(
    ("raw", "forbidden"),
    [
        ("contact 13800138000", "13800138000"),
        ("id 110101200003071234", "110101200003071234"),
        ("card 6222020200112345", "6222020200112345"),
        ("mail user.name@example.org", "user.name@example.org"),
        ("phone 13800138000 id 110101199003071234 mail a@b.com", "a@b.com"),
    ],
)
def test_sanitize_pii(raw: str, forbidden: str) -> None:
    result = _sanitize_pii(raw)
    assert forbidden not in result
    assert "***" in result


def test_sanitize_preserves_safe_text() -> None:
    assert _sanitize_pii("") == ""
    assert _sanitize_pii("error code 42 at line 100") == "error code 42 at line 100"


@pytest.mark.parametrize(
    ("pid", "message"),
    [
        ("pii-phone", "user phone 13800138000 failed"),
        ("pii-id", "id 110101199003071234 invalid"),
        ("pii-card", "card 6222020200112345 declined"),
        ("pii-email", "contact user@example.com failed"),
        (
            "pii-mixed",
            "contact 13800138000 id 110101199003071234 card 6222020200112345 email a@b.com",
        ),
    ],
)
def test_persisted_dlq_has_no_pii_in_any_string_field(pid: str, message: str) -> None:
    item = handle_failure(
        type("Pipeline", (), {"id": pid})(),
        TEST_SCOPE,
        RuntimeError(message),
        run_id=f"run-{pid}",
    )
    assert item is not None
    for field_name, field_value in item.items():
        if isinstance(field_value, str):
            for regex in _PII_REGEXES:
                assert not regex.search(field_value), f"{field_name} leaked PII"


def test_persisted_dlq_uses_allowlisted_fields_only() -> None:
    item = handle_failure(
        type("Pipeline", (), {"id": "pii-fields"})(),
        TEST_SCOPE,
        RuntimeError("token=secret password=hunter2"),
        run_id="run-pii-fields",
        metadata={"payload": {"private": "value"}, "safe": "ok"},
    )
    assert item is not None
    required = {
        "id", "pipelineId", "errorCode", "sourceErrorCode", "reason",
        "metadata", "payloadHash", "status", "retry_count", "max_retry",
        "createdAt", "updatedAt", "orgId", "projectId",
    }
    assert set(item) == required
    assert item["metadata"] == {"safe": "ok"}
    assert "secret" not in str(item)
    assert "hunter2" not in str(item)
