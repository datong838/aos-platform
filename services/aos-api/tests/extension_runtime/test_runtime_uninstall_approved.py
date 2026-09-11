"""The never-active uninstall branch is strict and does not weaken active cleanup."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.pq import TransactionStatus

from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard


class _Connection:
    info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)

    def __init__(self, counts=(0, 0, 0)) -> None:
        self.counts = counts
        self.statements: list[str] = []

    def execute(self, statement, _parameters=None):
        self.statements.append(statement)
        if "SELECT r.state FROM bundle_installation" in statement:
            return _Result({"state": "approved"})
        if "AS bindings" in statement:
            return _Result(dict(zip(("bindings", "unresolved", "unsafe"), self.counts)))
        raise AssertionError("active uninstall function must not run for approved installation")


class _Result:
    def __init__(self, row) -> None:
        self.row = row

    def fetchone(self):
        return self.row


def _invoke(conn: _Connection):
    return RuntimeUninstallGuard.before_uninstall(
        conn,
        org_id="org-org",
        project_id="dev-project",
        installation_id=uuid4(),
        expected_installation_revision=3,
        actor="runtime-owner",
    )


def test_approved_without_binding_or_unresolved_resource_is_noop() -> None:
    conn = _Connection()
    assert _invoke(conn) is None
    assert len(conn.statements) == 2


@pytest.mark.parametrize("counts", [(1, 0, 0), (0, 1, 0), (0, 0, 1)])
def test_approved_uninstall_rejects_binding_operation_or_unsafe_resource(counts) -> None:
    with pytest.raises(RuntimeConflict, match="not clean"):
        _invoke(_Connection(counts))
