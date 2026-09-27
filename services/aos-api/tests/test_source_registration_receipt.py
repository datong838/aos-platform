"""Source registration receipts bind the original key without exposing credentials."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from starlette.requests import Request

from aos_api import connector_registry, data_os_store
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


def _request(*headers: tuple[bytes, bytes]) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/v1/sources",
                    "headers": list(headers), "query_string": b""})


def _principal():
    return SimpleNamespace(org_id="org-org", project_id="dev-project")


def test_product_registration_passes_exact_key_without_exposing_secrets(monkeypatch):
    monkeypatch.setattr(wave_ext, "_connectors", {})
    monkeypatch.setattr(wave_ext, "_hydrate_data_os_scope", lambda _: None)
    monkeypatch.setattr(connector_registry, "assert_type_installed", lambda _: "jdbc-mysql-ssh")
    observed = []

    def persist(scope, item, **kwargs):
        observed.append((scope.key, kwargs["registration_key"], item["password"]))
        return {**item, "configurationRevision": "12345678-1234-1234-1234-123456789012"}

    monkeypatch.setattr(data_os_store, "persist_source", persist)
    body = wave_ext.ConnectorIn(id="source-one", type="jdbc-mysql-ssh", runtimeMode="direct",
        config={"sshHost": "example.invalid", "sshUser": "reader", "sshPassword": "synthetic-ssh",
                "dbHost": "127.0.0.1", "database": "shop", "username": "reader", "password": "synthetic-db"})
    result = wave_ext.create_source(body, _principal(), _request((b"idempotency-key", b"source-key-1")))
    assert observed == [(('org-org', 'dev-project'), 'source-key-1', 'synthetic-db')]
    assert result["configurationRevision"] == "12345678-1234-1234-1234-123456789012"
    assert "password" not in result and "sshPassword" not in result


def test_duplicate_registration_key_headers_fail_before_source_write(monkeypatch):
    monkeypatch.setattr(connector_registry, "assert_type_installed", lambda _: "file")
    with pytest.raises(wave_ext.ApiError) as error:
        wave_ext.create_source(wave_ext.ConnectorIn(id="source-one"), _principal(),
            _request((b"idempotency-key", b"one"), (b"idempotency-key", b"two")))
    assert error.value.code == "SOURCE_REGISTRATION_KEY_INVALID"


def test_receipt_get_is_tenant_scoped_and_not_found_is_distinct(monkeypatch):
    observed = []

    def read(scope, source_id, key):
        observed.append((scope.key, source_id, key))
        return {"sourceId": source_id, "configurationRevision": "12345678-1234-1234-1234-123456789012",
                "responseMetadata": {"id": source_id, "runtimeMode": "direct"}}

    monkeypatch.setattr(data_os_store, "load_source_registration_receipt", read)
    result = wave_ext.get_source_registration_receipt("source-one", "source-key-1", _principal())
    assert observed == [(('org-org', 'dev-project'), 'source-one', 'source-key-1')]
    assert result["responseMetadata"] == {"id": "source-one", "runtimeMode": "direct"}
    monkeypatch.setattr(data_os_store, "load_source_registration_receipt", lambda *_: None)
    with pytest.raises(wave_ext.ApiError) as error:
        wave_ext.get_source_registration_receipt("source-one", "source-key-1", _principal())
    assert error.value.code == "SOURCE_REGISTRATION_RECEIPT_NOT_FOUND"


def test_store_writes_source_and_receipt_once_and_replays_original_public_response(monkeypatch):
    revision = UUID("12345678-1234-1234-1234-123456789012")
    state = {"receipt": None, "source_writes": 0, "commits": 0}

    class Cursor:
        def __init__(self, row=None): self.row = row
        def fetchone(self): return self.row

    class Connection:
        def execute(self, query, params=None):
            if "SELECT request_hash,response_metadata FROM source_registration_receipt" in query:
                return Cursor(state["receipt"])
            if "SELECT configuration_revision FROM meta_source" in query:
                return Cursor(None)
            if "INSERT INTO meta_source" in query:
                state["source_writes"] += 1
                return Cursor({"props": {"runtimeMode": "direct", "password": "synthetic-db"},
                    "id": "source-one", "type": "jdbc-mysql-ssh", "status": "registered",
                    "plugin_id": "jdbc-mysql-ssh", "org_id": "org-org", "project_id": "dev-project",
                    "configuration_revision": revision})
            if "INSERT INTO source_registration_receipt" in query:
                import json
                state["receipt"] = {"request_hash": params[3], "response_metadata": json.loads(params[6])}
                return Cursor()
            assert "pg_advisory_xact_lock" in query
            return Cursor()
        def commit(self): state["commits"] += 1

    @contextmanager
    def connect(scope):
        assert scope.key == ("org-org", "dev-project")
        yield Connection()

    monkeypatch.setattr(data_os_store, "connect", connect)
    monkeypatch.setattr(data_os_store, "ensure_data_os_schema", lambda: None)
    scope = TenantScope("org-org", "dev-project")
    item = {"id": "source-one", "type": "jdbc-mysql-ssh", "password": "synthetic-db"}
    first = data_os_store.persist_source(scope, item, merge_existing=True,
        replace_fields=("password",), registration_key="original-key")
    again = data_os_store.persist_source(scope, item, merge_existing=True,
        replace_fields=("password",), registration_key="original-key")
    assert state["source_writes"] == 1 and state["commits"] == 1
    assert first["configurationRevision"] == again["configurationRevision"] == str(revision)
    assert "password" not in again and "password" not in state["receipt"]["response_metadata"]
    with pytest.raises(data_os_store.ApiError) as error:
        data_os_store.persist_source(scope, {**item, "password": "different"}, merge_existing=True,
            replace_fields=("password",), registration_key="original-key")
    assert error.value.code == "SOURCE_REGISTRATION_KEY_CONFLICT"
    assert state["source_writes"] == 1
