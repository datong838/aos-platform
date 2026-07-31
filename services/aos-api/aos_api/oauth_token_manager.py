"""Provider-neutral OAuth2 exchange, encrypted storage and lazy refresh."""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib import parse

from aos_api.kms_crypto import decrypt_strict, encrypt_strict
from aos_api.oauth_token_store import OAuthScope, OAuthTokenRecord, OAuthTokenStore
from aos_api.rest_connector import RestConnectorError, SafeUrlPolicy


class OAuthError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OAuthResponse:
    status: int
    data: dict[str, Any]
    headers: dict[str, str] | None = None
    final_url: str = ""


OAuthTransport = Callable[[str, dict[str, str], float], OAuthResponse]
AuditSink = Callable[[str, OAuthScope, dict[str, Any]], None]


class OAuthTokenManager:
    def __init__(self, store: OAuthTokenStore, transport: OAuthTransport, *, audit: AuditSink | None = None,
                 clock: Callable[[], datetime] | None = None, refresh_skew: timedelta = timedelta(minutes=5),
                 url_policy: SafeUrlPolicy | None = None) -> None:
        self.store, self.transport, self.audit = store, transport, audit or (lambda *_: None)
        self.clock, self.refresh_skew = clock or (lambda: datetime.now(timezone.utc)), refresh_skew
        self.url_policy = url_policy or SafeUrlPolicy()
        self._locks: dict[tuple[str, str, str, str], threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self.sleep: Callable[[float], None] = time.sleep

    @staticmethod
    def _aad(scope: OAuthScope, token_id: str, field: str) -> str:
        return "|".join((*scope.key, token_id, field))

    def _lock(self, scope: OAuthScope) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(scope.key, threading.Lock())

    def _emit(self, event: str, scope: OAuthScope, fields: dict[str, Any], started: float) -> None:
        self.audit(event, scope, {
            "platform": scope.platform,
            "externalAccountId": scope.external_account_id,
            "durationMs": max(0, int((time.monotonic() - started) * 1000)),
            **fields,
        })

    def exchange(self, scope: OAuthScope, *, token_endpoint: str, client_id: str, client_secret: str,
                 grant_type: str, code: str = "", redirect_uri: str = "", refresh_token: str = "",
                 timeout: float = 10) -> OAuthTokenRecord:
        started = time.monotonic()
        if grant_type not in {"authorization_code", "client_credentials", "refresh_token"}:
            raise OAuthError("OAUTH_GRANT_UNSUPPORTED")
        form = {"grant_type": grant_type, "client_id": client_id, "client_secret": client_secret}
        if grant_type == "authorization_code":
            form.update({"code": code, "redirect_uri": redirect_uri})
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise OAuthError("OAUTH_REFRESH_TOKEN_MISSING")
            form["refresh_token"] = refresh_token
        response = self._call(token_endpoint, form, timeout)
        if response.status >= 400:
            self._emit("oauth.exchange.failure", scope, {"status": "failed", "errorCode": self._error_code(response)}, started)
            raise OAuthError(self._error_code(response))
        try:
            record = self._record(scope, token_endpoint, client_id, client_secret, response.data)
        except (KeyError, TypeError, ValueError, OAuthError) as exc:
            self._emit("oauth.exchange.failure", scope, {"status": "failed", "errorCode": "OAUTH_RESPONSE_INVALID"}, started)
            raise OAuthError("OAUTH_RESPONSE_INVALID") from exc
        record = self.store.put(record)
        self._emit("oauth.exchange.success", scope, {"tokenId": record.token_id, "status": record.status}, started)
        return record

    def get_valid_access_token(self, scope: OAuthScope) -> str:
        record = self.store.get(scope)
        if not record or record.status != "active":
            raise OAuthError("OAUTH_REAUTH_REQUIRED")
        if record.expires_at is None or record.expires_at > self.clock() + self.refresh_skew:
            return self._decrypt(record, "access_token")
        with self._lock(scope):
            current = self.store.get(scope)
            if not current or current.status != "active":
                raise OAuthError("OAUTH_REAUTH_REQUIRED")
            if current.expires_at is None or current.expires_at > self.clock() + self.refresh_skew:
                return self._decrypt(current, "access_token")
            return self._refresh(current)

    def refresh_due(self) -> list[str]:
        refreshed: list[str] = []
        for record in self.store.list_due(self.clock() + self.refresh_skew):
            try:
                self.get_valid_access_token(record.scope)
                refreshed.append(record.token_id)
            except OAuthError:
                pass
        return refreshed

    def revoke(self, scope: OAuthScope) -> None:
        started = time.monotonic()
        record = self.store.get(scope)
        if not record:
            return
        record.status = "revoked"
        self.store.put(record, expected_version=record.version)
        self._emit("oauth.revoke.success", scope, {"tokenId": record.token_id, "status": "revoked"}, started)

    def _refresh(self, record: OAuthTokenRecord) -> str:
        started = time.monotonic()
        refresh_token = self._decrypt(record, "refresh_token") if record.encrypted_refresh_token else ""
        if not refresh_token:
            record.status = "reauth_required"
            self.store.put(record, expected_version=record.version)
            self._emit("oauth.reauth.required", record.scope, {"tokenId": record.token_id, "status": "reauth_required", "errorCode": "OAUTH_REFRESH_TOKEN_MISSING"}, started)
            raise OAuthError("OAUTH_REAUTH_REQUIRED")
        form = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": record.client_id,
                "client_secret": self._decrypt(record, "client_secret") if record.encrypted_client_secret else ""}
        response = self._call(record.token_endpoint, form, 10)
        if response.status >= 400:
            code = self._error_code(response)
            if code == "invalid_grant":
                record.status = "reauth_required"
                self.store.put(record, expected_version=record.version)
                self._emit("oauth.reauth.required", record.scope, {"tokenId": record.token_id, "status": "reauth_required", "errorCode": code}, started)
                raise OAuthError("OAUTH_REAUTH_REQUIRED")
            self._emit("oauth.refresh.failure", record.scope, {"tokenId": record.token_id, "status": "failed", "errorCode": code}, started)
            raise OAuthError("OAUTH_REFRESH_FAILED")
        data = response.data
        record.encrypted_access_token = encrypt_strict(str(data["access_token"]), aad=self._aad(record.scope, record.token_id, "access_token"))
        if data.get("refresh_token"):
            record.encrypted_refresh_token = encrypt_strict(str(data["refresh_token"]), aad=self._aad(record.scope, record.token_id, "refresh_token"))
        record.expires_at = self.clock() + timedelta(seconds=max(0, int(data.get("expires_in") or 0))) if data.get("expires_in") is not None else None
        self.store.put(record, expected_version=record.version)
        self._emit("oauth.refresh.success", record.scope, {"tokenId": record.token_id, "status": "active"}, started)
        return str(data["access_token"])

    def _record(self, scope: OAuthScope, endpoint: str, client_id: str, client_secret: str, data: dict[str, Any]) -> OAuthTokenRecord:
        if not data.get("access_token"):
            raise OAuthError("OAUTH_RESPONSE_INVALID")
        token_id = "oauth_" + secrets.token_hex(8)
        expires = self.clock() + timedelta(seconds=max(0, int(data.get("expires_in") or 0))) if data.get("expires_in") is not None else None
        record = OAuthTokenRecord(token_id=token_id, scope=scope, token_endpoint=endpoint,
                                  encrypted_access_token=encrypt_strict(str(data["access_token"]), aad=self._aad(scope, token_id, "access_token")),
                                  client_id=client_id, expires_at=expires, token_type=str(data.get("token_type") or "Bearer"),
                                  scopes=tuple(str(data.get("scope") or "").split()))
        if data.get("refresh_token"):
            record.encrypted_refresh_token = encrypt_strict(str(data["refresh_token"]), aad=self._aad(scope, token_id, "refresh_token"))
        if client_secret:
            record.encrypted_client_secret = encrypt_strict(client_secret, aad=self._aad(scope, token_id, "client_secret"))
        return record

    def _decrypt(self, record: OAuthTokenRecord, field: str) -> str:
        value = getattr(record, "encrypted_" + field)
        return decrypt_strict(value, aad=self._aad(record.scope, record.token_id, field))

    @staticmethod
    def _error_code(response: OAuthResponse) -> str:
        return str(response.data.get("error") or f"http_{response.status}")

    def _call(self, endpoint: str, form: dict[str, str], timeout: float) -> OAuthResponse:
        self._validate_endpoint(endpoint)
        retryable = {408, 429, 500, 502, 503, 504}
        for attempt in range(3):
            try:
                response = self.transport(endpoint, form, timeout)
            except (TimeoutError, OSError):
                response = OAuthResponse(504, {"error": "timeout"})
            self._validate_endpoint(response.final_url or endpoint)
            if response.status not in retryable or attempt == 2:
                return response
            raw = (response.headers or {}).get("Retry-After", "")
            try:
                delay = max(0.0, float(raw))
            except ValueError:
                delay = float(2 ** attempt)
            self.sleep(delay)
        raise OAuthError("OAUTH_UPSTREAM_FAILED")

    def _validate_endpoint(self, endpoint: str) -> None:
        parts = parse.urlsplit(endpoint)

        def looks_sensitive(key: str) -> bool:
            normalized = key.lower().replace("-", "_")
            return normalized in {"code", "api_key", "apikey"} or any(
                marker in normalized for marker in ("token", "secret", "password", "credential")
            )

        if any(looks_sensitive(key) for key, value in parse.parse_qsl(parts.query, keep_blank_values=True) if value):
            raise OAuthError("OAUTH_ENDPOINT_FORBIDDEN")
        try:
            self.url_policy.validate(endpoint)
        except RestConnectorError as exc:
            raise OAuthError("OAUTH_ENDPOINT_FORBIDDEN") from exc
