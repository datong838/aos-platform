from __future__ import annotations

from contextlib import contextmanager

from psycopg import IsolationLevel

from aos_api import db
from aos_api.tenant_scope import TenantScope


class _Connection:
    def __init__(self) -> None:
        self.isolation_level = None
        self.read_only = None
        self.statements: list[str] = []

    def execute(self, statement: str, params: object = None) -> object:
        del params
        self.statements.append(" ".join(statement.split()))
        return object()


@contextmanager
def _connection_context(connection: _Connection):
    yield connection


def test_read_only_connection_sets_transaction_characteristics_before_scope(
    monkeypatch,
) -> None:
    connection = _Connection()
    monkeypatch.setattr(
        db.psycopg,
        "connect",
        lambda *args, **kwargs: _connection_context(connection),
    )

    with db.connect_read_only(TenantScope("org-org", "dev-project")):
        pass

    assert connection.isolation_level == IsolationLevel.REPEATABLE_READ
    assert connection.read_only is True
    assert connection.statements == [
        "SET client_encoding TO 'UTF8'",
        "SET LOCAL ROLE aos_runtime",
        "SELECT set_config('aos.org_id', %s, true), set_config('aos.project_id', %s, true)",
    ]


def test_serializable_connection_remains_writable(monkeypatch) -> None:
    connection = _Connection()
    monkeypatch.setattr(
        db.psycopg,
        "connect",
        lambda *args, **kwargs: _connection_context(connection),
    )

    with db.connect_serializable(TenantScope("org-org", "dev-project")):
        pass

    assert connection.isolation_level == IsolationLevel.SERIALIZABLE
    assert connection.read_only is None


def test_default_connection_keeps_existing_read_write_characteristics(
    monkeypatch,
) -> None:
    connection = _Connection()
    monkeypatch.setattr(
        db.psycopg,
        "connect",
        lambda *args, **kwargs: _connection_context(connection),
    )

    with db.connect(TenantScope("org-org", "dev-project")):
        pass

    assert connection.isolation_level is None
    assert connection.read_only is None
