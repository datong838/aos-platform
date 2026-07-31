import base64
import threading
from datetime import datetime, timedelta, timezone

import pytest

from aos_api.oauth_token_manager import OAuthError, OAuthResponse, OAuthTokenManager
from aos_api.oauth_token_store import InMemoryOAuthTokenStore, OAuthScope


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("AOS_KMS_MASTER_KEY", base64.b64encode(b"k" * 32).decode())


def scope(org="o", workspace="w"):
    return OAuthScope(org, workspace, "GENERIC", "shop-1")


def test_exchange_encrypts_and_tenant_isolates():
    store = InMemoryOAuthTokenStore()
    manager = OAuthTokenManager(store, lambda *_: OAuthResponse(200, {"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600}))
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
    manager = OAuthTokenManager(InMemoryOAuthTokenStore(), transport)
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
    store = InMemoryOAuthTokenStore(); manager = OAuthTokenManager(store, transport, clock=lambda: now, refresh_skew=timedelta(minutes=5))
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="secret", grant_type="authorization_code", code="c")
    values = []
    threads = [threading.Thread(target=lambda: values.append(manager.get_valid_access_token(scope()))) for _ in range(5)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert values == ["new"] * 5
    assert calls == 2


def test_invalid_grant_requires_reauth_and_revoke_blocks_use():
    store = InMemoryOAuthTokenStore(); responses = [OAuthResponse(200, {"access_token": "a", "refresh_token": "r", "expires_in": 0}), OAuthResponse(400, {"error": "invalid_grant"})]
    manager = OAuthTokenManager(store, lambda *_: responses.pop(0), refresh_skew=timedelta(minutes=5))
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="s", grant_type="authorization_code", code="c")
    with pytest.raises(OAuthError, match="OAUTH_REAUTH_REQUIRED"): manager.get_valid_access_token(scope())
    assert store.get(scope()).status == "reauth_required"
    manager2 = OAuthTokenManager(InMemoryOAuthTokenStore(), lambda *_: OAuthResponse(200, {"access_token": "a"}))
    manager2.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="", grant_type="client_credentials")
    manager2.revoke(scope())
    with pytest.raises(OAuthError): manager2.get_valid_access_token(scope())


def test_audit_contains_no_secrets():
    events = []
    manager = OAuthTokenManager(InMemoryOAuthTokenStore(), lambda *_: OAuthResponse(200, {"access_token": "sensitive-access", "refresh_token": "sensitive-refresh"}), audit=lambda *args: events.append(args))
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
    manager = OAuthTokenManager(store, lambda *_: replies.pop(0))
    manager.sleep = lambda _: None
    manager.exchange(scope(), token_endpoint="https://oauth.example/token", client_id="id", client_secret="s", grant_type="authorization_code", code="c")
    assert manager.get_valid_access_token(scope()) == "new"
