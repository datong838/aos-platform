import base64
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from aos_api.oauth_token_manager import OAuthError, OAuthResponse, OAuthTokenManager
from aos_api.oauth_token_store import InMemoryOAuthTokenStore, OAuthScope, OAuthTokenRecord, PostgresOAuthTokenStore
from aos_api.rest_connector import SafeUrlPolicy


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("AOS_KMS_MASTER_KEY", base64.b64encode(b"k" * 32).decode())


def scope(org="o", workspace="w"):
    return OAuthScope(org, workspace, "GENERIC", "shop-1")


def oauth_manager(store, transport, **kwargs):
    kwargs.setdefault("url_policy", SafeUrlPolicy(resolver=lambda *_: [(None, None, None, None, ("93.184.216.34", 443))]))
    return OAuthTokenManager(store, transport, **kwargs)


def test_exchange_encrypts_and_tenant_isolates():
    store = InMemoryOAuthTokenStore()
    manager = oauth_manager(store, lambda *_: OAuthResponse(200, {"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600}))
    record = manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="client-secret", grant_type="authorization_code", code="code")
    assert "access-secret" not in record.encrypted_access_token
    assert manager.get_valid_access_token(scope()) == "access-secret"
    with pytest.raises(OAuthError, match="OAUTH_REAUTH_REQUIRED"):
        manager.get_valid_access_token(scope(org="other"))


def test_explicit_refresh_token_grant_is_supported():
    captured = {}
    def transport(_url, form, _timeout):
        captured.update(form)
        return OAuthResponse(200, {"access_token": "new-access", "refresh_token": "new-refresh"})
    manager = oauth_manager(InMemoryOAuthTokenStore(), transport)
    record = manager.exchange(
        scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="secret",
        grant_type="refresh_token", refresh_token="old-refresh")
    assert captured["grant_type"] == "refresh_token" and captured["refresh_token"] == "old-refresh"
    assert "new-access" not in record.encrypted_access_token


def test_lazy_refresh_rotation_and_single_flight():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc); calls = 0; gate = threading.Lock()
    def transport(_url, form, _timeout):
        nonlocal calls
        with gate: calls += 1
        if form["grant_type"] == "authorization_code":
            return OAuthResponse(200, {"access_token": "old", "refresh_token": "r1", "expires_in": 1})
        return OAuthResponse(200, {"access_token": "new", "refresh_token": "r2", "expires_in": 3600})
    store = InMemoryOAuthTokenStore(); manager = oauth_manager(store, transport, clock=lambda: now, refresh_skew=timedelta(minutes=5))
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="secret", grant_type="authorization_code", code="c")
    values = []
    threads = [threading.Thread(target=lambda: values.append(manager.get_valid_access_token(scope()))) for _ in range(5)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert values == ["new"] * 5
    assert calls == 2


def test_invalid_grant_requires_reauth_and_revoke_blocks_use():
    store = InMemoryOAuthTokenStore(); responses = [OAuthResponse(200, {"access_token": "a", "refresh_token": "r", "expires_in": 0}), OAuthResponse(400, {"error": "invalid_grant"})]
    manager = oauth_manager(store, lambda *_: responses.pop(0), refresh_skew=timedelta(minutes=5))
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="s", grant_type="authorization_code", code="c")
    with pytest.raises(OAuthError, match="OAUTH_REAUTH_REQUIRED"): manager.get_valid_access_token(scope())
    assert store.get(scope()).status == "reauth_required"
    manager2 = oauth_manager(InMemoryOAuthTokenStore(), lambda *_: OAuthResponse(200, {"access_token": "a"}))
    manager2.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="", grant_type="client_credentials")
    manager2.revoke(scope())
    with pytest.raises(OAuthError): manager2.get_valid_access_token(scope())


def test_audit_contains_no_secrets():
    events = []
    manager = oauth_manager(InMemoryOAuthTokenStore(), lambda *_: OAuthResponse(200, {"access_token": "sensitive-access", "refresh_token": "sensitive-refresh"}), audit=lambda *args: events.append(args))
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="sensitive-client", grant_type="client_credentials")
    assert "sensitive" not in repr(events)


def test_refresh_retries_429_and_5xx():
    store = InMemoryOAuthTokenStore()
    replies = [
        OAuthResponse(200, {"access_token": "old", "refresh_token": "r", "expires_in": 0}),
        OAuthResponse(429, {"error": "limited"}, {"Retry-After": "0"}),
        OAuthResponse(503, {"error": "down"}),
        OAuthResponse(200, {"access_token": "new", "expires_in": 3600}),
    ]
    manager = oauth_manager(store, lambda *_: replies.pop(0))
    manager.sleep = lambda _: None
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="s", grant_type="authorization_code", code="c")
    assert manager.get_valid_access_token(scope()) == "new"


@pytest.mark.parametrize("endpoint", [
    "http://oauth.example.test/token",
    "https://user:pwd@oauth.example.test/token",
    "https://oauth.example.test/token?access_token=leak",
])
def test_oauth_endpoint_rejects_unsafe_urls_before_transport(endpoint):
    calls = []
    manager = oauth_manager(InMemoryOAuthTokenStore(), lambda *_: calls.append(1))
    with pytest.raises(OAuthError, match="OAUTH_ENDPOINT_FORBIDDEN"):
        manager.exchange(scope(), token_endpoint=endpoint, client_id="id", client_secret="secret", grant_type="client_credentials")
    assert calls == []


def test_oauth_redirect_target_is_revalidated():
    manager = oauth_manager(
        InMemoryOAuthTokenStore(),
        lambda *_: OAuthResponse(200, {"access_token": "secret"}, final_url="https://127.0.0.1/token"),
    )
    with pytest.raises(OAuthError, match="OAUTH_ENDPOINT_FORBIDDEN"):
        manager.exchange(scope(), token_endpoint="https://oauth.example.test/token", client_id="id", client_secret="secret", grant_type="client_credentials")


def test_refresh_revalidates_stored_token_endpoint():
    calls = 0
    def transport(*_):
        nonlocal calls
        calls += 1
        return OAuthResponse(200, {"access_token": "old", "refresh_token": "refresh", "expires_in": 0})
    store = InMemoryOAuthTokenStore()
    manager = oauth_manager(store, transport)
    manager.exchange(scope(), token_endpoint="https://oauth.example.test/token", client_id="id", client_secret="secret", grant_type="authorization_code", code="c")
    record = store.get(scope())
    record.token_endpoint = "https://169.254.169.254/token"
    store.put(record, expected_version=record.version)
    with pytest.raises(OAuthError, match="OAUTH_ENDPOINT_FORBIDDEN"):
        manager.get_valid_access_token(scope())
    assert calls == 1


def test_in_memory_store_returns_detached_records_and_conflict_does_not_pollute():
    store = InMemoryOAuthTokenStore()
    manager = oauth_manager(store, lambda *_: OAuthResponse(200, {"access_token": "access", "expires_in": 3600}))
    manager.exchange(scope(), token_endpoint="https://oauth.example.test/token", client_id="id", client_secret="secret", grant_type="client_credentials")
    detached = store.get(scope())
    detached.status = "revoked"
    assert store.get(scope()).status == "active"
    due = store.list_due(datetime.now(timezone.utc) + timedelta(hours=2))
    due[0].status = "revoked"
    assert store.get(scope()).status == "active"
    detached.version = 0
    with pytest.raises(RuntimeError, match="OAUTH_TOKEN_VERSION_CONFLICT"):
        store.put(detached, expected_version=0)
    stored = store.get(scope())
    assert stored.status == "active" and stored.version == 1
    stored.status = "reauth_required"
    saved = store.put(stored, expected_version=stored.version)
    stored.status = "revoked"
    assert saved.status == "reauth_required" and store.get(scope()).status == "reauth_required"


def test_postgres_upsert_returns_payload_with_database_version(monkeypatch):
    statements = []
    class Cursor:
        def __init__(self, row): self.row = row
        def fetchone(self): return self.row
    class Connection:
        def execute(self, sql, params):
            statements.append(sql)
            payload = json.loads(params[4])
            payload["version"] = 7
            return Cursor({"payload": payload})
        def commit(self): pass
    @contextmanager
    def connect():
        yield Connection()
    from aos_api import db
    monkeypatch.setattr(db, "connect", connect)
    original = OAuthTokenRecord("token", scope(), "https://oauth.example.test/token", "enc:v2:value")
    saved = PostgresOAuthTokenStore().put(original)
    assert original.version == 1
    assert saved.version == 7
    assert "jsonb_set" in statements[0] and "RETURNING payload" in statements[0]
