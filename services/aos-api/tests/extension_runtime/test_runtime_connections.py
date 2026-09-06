from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus


class _Connection:
    def __init__(self):
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        self.read_only = False
        self.isolation_level = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_worker_connection_starts_idle_without_scope_or_sql(monkeypatch):
    from aos_api.extension_runtime import runtime_connections
    connection = _Connection()
    calls = []
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "runtime")
    monkeypatch.setattr(runtime_connections, "get_dsn", lambda: "web")
    monkeypatch.setattr(runtime_connections.psycopg, "connect", lambda *a, **k: calls.append((a, k)) or connection)
    with runtime_connections.runtime_worker_connection() as opened:
        assert opened is connection
    assert calls[0][1]["row_factory"] is not None


def test_worker_connection_requires_a_distinct_configured_identity(monkeypatch):
    from aos_api.extension_runtime import runtime_connections
    monkeypatch.delenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        with runtime_connections.runtime_worker_connection():
            pass
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "same")
    monkeypatch.setattr(runtime_connections, "get_dsn", lambda: "same")
    with pytest.raises(RuntimeError, match="differ"):
        with runtime_connections.runtime_worker_connection():
            pass


def test_directory_connection_requires_distinct_dsn_and_sets_read_only(monkeypatch):
    from aos_api.extension_runtime import runtime_connections
    monkeypatch.delenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        with runtime_connections.runtime_directory_connection():
            pass
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "same")
    monkeypatch.setattr(runtime_connections, "get_dsn", lambda: "same")
    with pytest.raises(RuntimeError, match="differ"):
        with runtime_connections.runtime_directory_connection():
            pass
    connection = _Connection()
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "directory")
    monkeypatch.setattr(runtime_connections.psycopg, "connect", lambda *a, **k: connection)
    with runtime_connections.runtime_directory_connection() as opened:
        assert opened.read_only is True
        assert opened.isolation_level is not None
