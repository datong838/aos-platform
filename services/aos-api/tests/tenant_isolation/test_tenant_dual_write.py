from __future__ import annotations

import pytest
from aos_api.errors import ApiError
from aos_api.openfga import write_tuple
from aos_api.tenant_dual_write import (
    DualWriteMode,
    authz_dual_write_mode,
    stable_key_hash,
)
from aos_api.tenant_scope import TenantScope


class Result:
    def __init__(self, row=None) -> None:
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, observed=None) -> None:
        self.observed = observed
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, query: str, values: tuple):
        normalized = " ".join(query.split())
        self.calls.append((normalized, values))
        if normalized.startswith("SELECT org_id, project_id"):
            return Result(self.observed)
        return Result()


def test_dual_write_mode_defaults_off_and_rejects_unknown(monkeypatch) -> None:
    monkeypatch.delenv("AOS_TENANT_DUAL_WRITE_AUTHZ", raising=False)
    assert authz_dual_write_mode() is DualWriteMode.OFF
    with pytest.raises(RuntimeError, match="must be off, shadow, or enforce"):
        authz_dual_write_mode("maybe")


def test_off_preserves_legacy_insert_without_ledger() -> None:
    conn = FakeConnection()
    write_tuple(
        conn,
        "user:alice",
        "viewer",
        "object:1",
        scope=TenantScope("org-a", "project-a"),
        dual_write_mode="off",
    )

    assert len(conn.calls) == 1
    assert "org_id" not in conn.calls[0][0]
    assert "tenant_dual_write_ledger" not in conn.calls[0][0]


def test_shadow_writes_scope_and_hash_only_match_evidence() -> None:
    scope = TenantScope("org-a", "project-a")
    conn = FakeConnection(observed={"org_id": "org-a", "project_id": "project-a"})
    write_tuple(
        conn,
        "user:alice",
        "viewer",
        "object:1",
        scope=scope,
        dual_write_mode="shadow",
    )

    assert len(conn.calls) == 3
    ledger_query, ledger_values = conn.calls[-1]
    assert "tenant_dual_write_ledger" in ledger_query
    assert ledger_values[-1] == "MATCH"
    assert len(ledger_values[4]) == 64
    assert "user:alice" not in ledger_values
    assert "object:1" not in ledger_values


def test_shadow_records_existing_unscoped_tuple_without_backfill() -> None:
    conn = FakeConnection(observed={"org_id": None, "project_id": None})
    write_tuple(
        conn,
        "user:legacy",
        "viewer",
        "object:legacy",
        scope=TenantScope("org-a", "project-a"),
        dual_write_mode="shadow",
    )

    assert "ON CONFLICT DO NOTHING" in conn.calls[0][0]
    assert "DO UPDATE" not in conn.calls[0][0]
    assert conn.calls[-1][1][-1] == "MISMATCH"
    assert conn.calls[-1][1][5:7] == (None, None)


def test_enforce_fails_closed_on_scope_conflict() -> None:
    conn = FakeConnection(observed={"org_id": "org-b", "project_id": "project-b"})
    with pytest.raises(ApiError) as exc_info:
        write_tuple(
            conn,
            "user:alice",
            "viewer",
            "object:1",
            scope=TenantScope("org-a", "project-a"),
            dual_write_mode="enforce",
        )
    assert exc_info.value.code == "TENANT_DUAL_WRITE_CONFLICT"
    assert conn.calls[-1][1][-1] == "MISMATCH"


def test_stable_key_hash_is_deterministic_and_redacted() -> None:
    digest = stable_key_hash("user:alice", "viewer", "object:1")
    assert digest == stable_key_hash("user:alice", "viewer", "object:1")
    assert len(digest) == 64
    assert "alice" not in digest
