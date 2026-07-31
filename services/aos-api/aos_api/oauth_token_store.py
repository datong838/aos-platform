"""Tenant-scoped OAuth token persistence contracts and PostgreSQL adapter."""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class OAuthScope:
    org_id: str
    workspace_id: str
    platform: str
    external_account_id: str

    def __post_init__(self) -> None:
        values = (self.org_id, self.workspace_id, self.platform, self.external_account_id)
        if any(not value.strip() for value in values):
            raise ValueError("OAuth scope fields must not be empty")
        object.__setattr__(self, "platform", self.platform.strip().lower())

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.org_id, self.workspace_id, self.platform, self.external_account_id)


@dataclass
class OAuthTokenRecord:
    token_id: str
    scope: OAuthScope
    token_endpoint: str
    encrypted_access_token: str
    encrypted_refresh_token: str = ""
    encrypted_client_secret: str = ""
    client_id: str = ""
    token_type: str = "Bearer"
    scopes: tuple[str, ...] = ()
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    status: str = "active"
    version: int = 1
    updated_at: datetime | None = None


class OAuthTokenStore(Protocol):
    def get(self, scope: OAuthScope) -> OAuthTokenRecord | None: ...
    def put(self, record: OAuthTokenRecord, *, expected_version: int | None = None) -> OAuthTokenRecord: ...
    def list_due(self, before: datetime) -> list[OAuthTokenRecord]: ...
    def delete(self, scope: OAuthScope) -> bool: ...


class InMemoryOAuthTokenStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str, str], OAuthTokenRecord] = {}
        self._lock = threading.RLock()

    def get(self, scope: OAuthScope) -> OAuthTokenRecord | None:
        with self._lock:
            return self._items.get(scope.key)

    def put(self, record: OAuthTokenRecord, *, expected_version: int | None = None) -> OAuthTokenRecord:
        with self._lock:
            current = self._items.get(record.scope.key)
            if expected_version is not None and (current is None or current.version != expected_version):
                raise RuntimeError("OAUTH_TOKEN_VERSION_CONFLICT")
            record.version = (current.version + 1) if current else 1
            record.updated_at = datetime.now(timezone.utc)
            self._items[record.scope.key] = record
            return record

    def list_due(self, before: datetime) -> list[OAuthTokenRecord]:
        with self._lock:
            return [r for r in self._items.values() if r.status == "active" and r.expires_at and r.expires_at <= before]

    def delete(self, scope: OAuthScope) -> bool:
        with self._lock:
            return self._items.pop(scope.key, None) is not None


class PostgresOAuthTokenStore:
    """Dedicated-table adapter. Schema is managed by the accompanying migration."""

    def get(self, scope: OAuthScope) -> OAuthTokenRecord | None:
        from aos_api.db import connect
        with connect() as conn:
            row = conn.execute(
                "SELECT payload FROM oauth_token_store WHERE org_id=%s AND workspace_id=%s AND platform=%s AND external_account_id=%s",
                scope.key,
            ).fetchone()
        return self._decode(row["payload"] if row else None)

    def put(self, record: OAuthTokenRecord, *, expected_version: int | None = None) -> OAuthTokenRecord:
        from aos_api.db import connect
        current = self.get(record.scope)
        if expected_version is not None and (current is None or current.version != expected_version):
            raise RuntimeError("OAUTH_TOKEN_VERSION_CONFLICT")
        record.version = (current.version + 1) if current else 1
        record.updated_at = datetime.now(timezone.utc)
        payload = self._encode(record)
        with connect() as conn:
            if expected_version is not None:
                cur = conn.execute(
                    """UPDATE oauth_token_store SET payload=%s::jsonb,version=%s,expires_at=%s,updated_at=NOW()
                    WHERE org_id=%s AND workspace_id=%s AND platform=%s AND external_account_id=%s AND version=%s""",
                    (payload, record.version, record.expires_at, *record.scope.key, expected_version),
                )
                if cur.rowcount != 1:
                    conn.rollback()
                    raise RuntimeError("OAUTH_TOKEN_VERSION_CONFLICT")
            else:
                conn.execute(
                    """INSERT INTO oauth_token_store(org_id,workspace_id,platform,external_account_id,payload,version,expires_at,updated_at)
                    VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s,NOW())
                    ON CONFLICT(org_id,workspace_id,platform,external_account_id) DO UPDATE SET
                      payload=EXCLUDED.payload,version=oauth_token_store.version+1,expires_at=EXCLUDED.expires_at,updated_at=NOW()""",
                    (*record.scope.key, payload, record.version, record.expires_at),
                )
            conn.commit()
        return record

    def list_due(self, before: datetime) -> list[OAuthTokenRecord]:
        from aos_api.db import connect
        with connect() as conn:
            rows = conn.execute("SELECT payload FROM oauth_token_store WHERE expires_at IS NOT NULL AND expires_at <= %s", (before,)).fetchall()
        return [item for row in rows if (item := self._decode(row["payload"])) and item.status == "active"]

    def delete(self, scope: OAuthScope) -> bool:
        from aos_api.db import connect
        with connect() as conn:
            cur = conn.execute("DELETE FROM oauth_token_store WHERE org_id=%s AND workspace_id=%s AND platform=%s AND external_account_id=%s", scope.key)
            conn.commit()
            return bool(cur.rowcount)

    @staticmethod
    def _encode(record: OAuthTokenRecord) -> str:
        data = asdict(record)
        data["scope"] = asdict(record.scope)
        for field in ("expires_at", "refresh_expires_at", "updated_at"):
            data[field] = data[field].isoformat() if data[field] else None
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _decode(payload) -> OAuthTokenRecord | None:
        if not payload:
            return None
        data = json.loads(payload) if isinstance(payload, str) else dict(payload)
        data["scope"] = OAuthScope(**data["scope"])
        data["scopes"] = tuple(data.get("scopes") or ())
        for field in ("expires_at", "refresh_expires_at", "updated_at"):
            data[field] = datetime.fromisoformat(data[field]) if data.get(field) else None
        return OAuthTokenRecord(**data)
