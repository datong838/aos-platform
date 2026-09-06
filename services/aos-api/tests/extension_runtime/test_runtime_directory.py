from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.runtime_directory import PostgresRuntimeTenantDirectory
from aos_api.extension_runtime.runtime_host import RuntimeTenantAssignment


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Connection:
    def __init__(self, rows, status=TransactionStatus.IDLE):
        self.rows = rows
        self.info = SimpleNamespace(transaction_status=status)
        self.executed = []

    def transaction(self):
        return _Transaction()

    def execute(self, statement):
        self.executed.append(statement)
        return self

    def fetchall(self):
        return list(self.rows)


def _directory(rows, built, *, status=TransactionStatus.IDLE):
    connection = _Connection(rows, status=status)

    @contextmanager
    def connect():
        yield connection

    def build(*, scope, assignment_revision):
        built.append((scope.key, assignment_revision))
        worker = object.__new__(__import__(
            "aos_api.extension_runtime.resource_recovery", fromlist=["ExpiredResourceRecovery"]
        ).ExpiredResourceRecovery)
        return RuntimeTenantAssignment(scope=scope, recovery=worker)

    return PostgresRuntimeTenantDirectory(connect=connect, build_assignment=build), connection


def test_directory_reuses_exact_assignment_until_global_scope_revision_changes():
    built = []
    rows = [dict(org_id="b", project_id="two", assignment_revision=4),
            dict(org_id="a", project_id="one", assignment_revision=3)]
    directory, connection = _directory(rows, built)
    first = directory()
    second = directory()
    assert tuple(item.scope.key for item in first) == (("a", "one"), ("b", "two"))
    assert first[0] is second[0] and first[1] is second[1]
    assert built == [(('b', 'two'), 4), (('a', 'one'), 3)]
    assert connection.executed == [
        "SELECT org_id,project_id,assignment_revision FROM extension_runtime_read_host_assignments()",
        "SELECT org_id,project_id,assignment_revision FROM extension_runtime_read_host_assignments()",
    ]
    connection.rows = [dict(org_id="a", project_id="one", assignment_revision=4)]
    third = directory()
    assert third[0] is not first[0]
    assert built[-1] == (("a", "one"), 4)


@pytest.mark.parametrize("case", ["duplicate", "revision", "overflow", "busy", "wrong_scope", "async"])
def test_directory_rejects_untrusted_or_unbounded_results(case):
    built = []
    rows = [dict(org_id="a", project_id="one", assignment_revision=1)]
    if case == "duplicate":
        rows *= 2
    elif case == "revision":
        rows[0]["assignment_revision"] = True
    elif case == "overflow":
        rows = [dict(org_id="a", project_id=str(i), assignment_revision=1) for i in range(1001)]
    directory, _ = _directory(rows, built, status=(TransactionStatus.INTRANS if case == "busy" else TransactionStatus.IDLE))
    if case == "wrong_scope":
        directory._build = lambda **_: RuntimeTenantAssignment(
            scope=TenantScope("x", "other"),
            recovery=object.__new__(__import__(
                "aos_api.extension_runtime.resource_recovery", fromlist=["ExpiredResourceRecovery"]
            ).ExpiredResourceRecovery),
        )
    if case == "async":
        async def deferred(**_):
            return None
        directory._build = deferred
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        directory()


def test_directory_requires_synchronous_dependencies():
    async def deferred():
        return ()
    with pytest.raises(ValueError):
        PostgresRuntimeTenantDirectory(connect=deferred, build_assignment=lambda **_: None)
