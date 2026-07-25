"""Model Provider Credential Engine — 222plan Phase A.

供应商凭据管理引擎：CRUD + 加密存储 + 轮换策略 + 连接测试。

对应 222 文档第 23 章 Tab 1 凭据管理。
"""
from __future__ import annotations

import secrets as _secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from aos_api.kms_crypto import decrypt, encrypt, is_encrypted, mask_key
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.provider_credential")

_KV_KEY = "model_provider_credentials"

# Rotation policy → days
_ROTATION_DAYS: dict[str, int] = {
    "manual": 0,
    "30d": 30,
    "90d": 90,
}


class RotationRecord(BaseModel):
    date: str
    operator: str = "system"
    old_key_tail: str = ""


class ProviderCredential(BaseModel):
    key_id: str
    provider_id: str
    label: str = "默认"
    key_masked: str = ""
    encrypted_key: str = ""
    rotation_policy: str = "manual"  # manual / 30d / 90d
    last_rotated_at: str = ""
    next_rotation_at: str = ""
    rotation_history: list[RotationRecord] = Field(default_factory=list)
    created_at: str = ""


class ProviderCredentialEngine:
    """Singleton credential store with threading.Lock.

    Storage: in-memory dict {provider_id: [ProviderCredential, ...]}.
    Persisted to aip_kv_store on every mutation.
    """

    _instance: ProviderCredentialEngine | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ProviderCredentialEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._create()
        return cls._instance

    @classmethod
    def _create(cls) -> ProviderCredentialEngine:
        self = super().__new__(cls)
        self._store: dict[str, list[ProviderCredential]] = {}
        self._load()
        return self

    # ── persistence ────────────────────────────────────────────

    def _load(self) -> None:
        from aos_api.aip_kv_store import get_payload

        raw = get_payload(_KV_KEY)
        if not raw or not isinstance(raw, dict):
            return
        by_id = raw.get("byProvider") or {}
        for pid, items in by_id.items():
            if not isinstance(items, list):
                continue
            creds = []
            for item in items:
                try:
                    creds.append(ProviderCredential(**item))
                except Exception:
                    pass
            if creds:
                self._store[pid] = creds
        log.info("credential_load providers=%d", len(self._store))

    def _save(self) -> None:
        from aos_api.aip_kv_store import put_payload

        data = {
            "byProvider": {
                pid: [c.model_dump() for c in creds]
                for pid, creds in self._store.items()
            }
        }
        put_payload(_KV_KEY, data)

    # ── CRUD ───────────────────────────────────────────────────

    def list_credentials(self, provider_id: str) -> list[ProviderCredential]:
        """Return all credentials for a provider (masked, no raw key)."""
        return list(self._store.get(provider_id, []))

    def create_credential(
        self,
        provider_id: str,
        api_key: str,
        label: str = "默认",
        rotation_policy: str = "manual",
        operator: str = "system",
    ) -> ProviderCredential:
        """Create a new credential with encrypted storage."""
        now = datetime.now(timezone.utc)
        key_id = f"cred_{_secrets.token_hex(8)}"
        encrypted = encrypt(api_key)
        masked = mask_key(api_key)
        days = _ROTATION_DAYS.get(rotation_policy, 0)
        next_rot = ""
        if days > 0:
            next_rot = (now + timedelta(days=days)).isoformat()
        elif self._store.get(provider_id):
            # Inherit from existing
            existing = self._store[provider_id][0]
            days = _ROTATION_DAYS.get(existing.rotation_policy, 0)
            if days > 0:
                next_rot = (now + timedelta(days=days)).isoformat()

        cred = ProviderCredential(
            key_id=key_id,
            provider_id=provider_id,
            label=label,
            key_masked=masked,
            encrypted_key=encrypted,
            rotation_policy=rotation_policy,
            last_rotated_at=now.isoformat(),
            next_rotation_at=next_rot,
            rotation_history=[],
            created_at=now.isoformat(),
        )
        items = self._store.setdefault(provider_id, [])
        items.append(cred)
        self._save()
        log.info("credential_create provider=%s key_id=%s", provider_id, key_id)
        return cred

    def update_credential(
        self,
        provider_id: str,
        key_id: str,
        api_key: str | None = None,
        label: str | None = None,
        rotation_policy: str | None = None,
        operator: str = "system",
    ) -> ProviderCredential | None:
        """Update a credential. If api_key changes, record rotation."""
        items = self._store.get(provider_id, [])
        for i, c in enumerate(items):
            if c.key_id != key_id:
                continue
            now = datetime.now(timezone.utc)
            old_tail = c.key_masked

            if api_key and api_key != decrypt(c.encrypted_key):
                # Key rotation
                c.encrypted_key = encrypt(api_key)
                c.key_masked = mask_key(api_key)
                c.last_rotated_at = now.isoformat()
                c.rotation_history.append(
                    RotationRecord(
                        date=now.isoformat(),
                        operator=operator,
                        old_key_tail=old_tail,
                    )
                )
                # Keep only last 5
                c.rotation_history = c.rotation_history[-5:]

            if label is not None:
                c.label = label
            if rotation_policy is not None:
                c.rotation_policy = rotation_policy
                days = _ROTATION_DAYS.get(rotation_policy, 0)
                c.next_rotation_at = (
                    (now + timedelta(days=days)).isoformat() if days > 0 else ""
                )

            items[i] = c
            self._save()
            log.info("credential_update provider=%s key_id=%s", provider_id, key_id)
            return c
        return None

    def delete_credential(self, provider_id: str, key_id: str) -> bool:
        """Delete a credential by key_id."""
        items = self._store.get(provider_id, [])
        before = len(items)
        items = [c for c in items if c.key_id != key_id]
        if len(items) < before:
            self._store[provider_id] = items
            self._save()
            log.info("credential_delete provider=%s key_id=%s", provider_id, key_id)
            return True
        return False

    def get_credential(self, provider_id: str, key_id: str) -> ProviderCredential | None:
        """Get a single credential by key_id."""
        for c in self._store.get(provider_id, []):
            if c.key_id == key_id:
                return c
        return None

    def resolve_api_key(self, provider_id: str) -> str:
        """Get the active (decrypted) API key for a provider.

        Returns the most recently created credential's key,
        or empty string if none exists.
        """
        items = self._store.get(provider_id, [])
        if not items:
            return ""
        # Use the last created credential
        return decrypt(items[-1].encrypted_key)

    def has_credentials(self, provider_id: str) -> bool:
        """Check if a provider has any credentials."""
        return bool(self._store.get(provider_id))

    def check_rotation_due(self, provider_id: str) -> list[ProviderCredential]:
        """Return credentials that are due for rotation."""
        now = datetime.now(timezone.utc)
        due = []
        for c in self._store.get(provider_id, []):
            if not c.next_rotation_at:
                continue
            try:
                next_dt = datetime.fromisoformat(c.next_rotation_at)
                if next_dt <= now:
                    due.append(c)
            except Exception:
                pass
        return due

    def migrate_legacy_secret(self, provider_id: str, plaintext_key: str) -> None:
        """Migrate a legacy plaintext key to encrypted storage.

        Called during llm_provider_registry.py integration.
        Only migrates if no credential exists yet.
        """
        if not plaintext_key:
            return
        if self.has_credentials(provider_id):
            return  # Already has credentials
        if is_encrypted(plaintext_key):
            return  # Already encrypted
        self.create_credential(
            provider_id=provider_id,
            api_key=plaintext_key,
            label="迁移导入",
            rotation_policy="manual",
            operator="migration",
        )
        log.info("credential_migrate provider=%s", provider_id)


# ── Singleton getter ──────────────────────────────────────────

_engine: ProviderCredentialEngine | None = None
_engine_lock = threading.Lock()


def get_credential_engine() -> ProviderCredentialEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ProviderCredentialEngine()
    return _engine
