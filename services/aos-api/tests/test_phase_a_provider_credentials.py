"""Phase A · 222plan — Model Provider Credential + KMS Crypto + Security + Call Log tests.

Tests:
  - KMS encrypt/decrypt (5 cases)
  - Credential CRUD (6 cases)
  - Credential API (5 cases)
  - Provider Security (3 cases)
  - Call Log (3 cases)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure services dir is importable
_services = Path(__file__).resolve().parents[1]
if str(_services) not in sys.path:
    sys.path.insert(0, str(_services))

import pytest
from fastapi.testclient import TestClient


# ── KMS Crypto Tests ──────────────────────────────────────────


class TestKMSCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        from aos_api.kms_crypto import decrypt, encrypt

        plaintext = "sk-test-key-1234567890abcdef"
        token = encrypt(plaintext)
        assert token != plaintext
        assert decrypt(token) == plaintext

    def test_encrypt_produces_prefix(self):
        from aos_api.kms_crypto import encrypt, is_encrypted

        token = encrypt("my-secret-key")
        assert is_encrypted(token)
        assert token.startswith("enc:v1:")

    def test_decrypt_plaintext_passthrough(self):
        """Legacy plaintext values should pass through decrypt unchanged."""
        from aos_api.kms_crypto import decrypt

        assert decrypt("sk-legacy-plaintext-key") == "sk-legacy-plaintext-key"
        assert decrypt("") == ""

    def test_is_encrypted(self):
        from aos_api.kms_crypto import is_encrypted

        assert is_encrypted("enc:v1:abc123")
        assert not is_encrypted("sk-plaintext")
        assert not is_encrypted("")

    def test_mask_key(self):
        from aos_api.kms_crypto import mask_key

        assert mask_key("sk-1234567890abcdef") == "...cdef"
        assert mask_key("ab") == "**"
        assert mask_key("") == ""
        assert mask_key("1234") == "****"  # len == visible_tail → all masked


# ── Credential Engine Tests ───────────────────────────────────


class TestProviderCredentialEngine:
    def test_create_credential(self):
        from aos_api.model_provider_credential import get_credential_engine

        engine = get_credential_engine()
        cred = engine.create_credential(
            provider_id="test-openai",
            api_key="sk-test-create-12345",
            label="测试",
        )
        assert cred.provider_id == "test-openai"
        assert cred.label == "测试"
        assert cred.key_masked == "...13245"[-4:] or cred.key_masked.endswith("2345")
        assert cred.key_id.startswith("cred_")

    def test_list_credentials(self):
        from aos_api.model_provider_credential import get_credential_engine

        engine = get_credential_engine()
        engine.create_credential(
            provider_id="test-list",
            api_key="sk-list-test-key",
        )
        items = engine.list_credentials("test-list")
        assert len(items) >= 1
        # Ensure no raw key in output
        for item in items:
            assert "sk-list-test-key" not in item.model_dump().get("encrypted_key", "")

    def test_update_credential_rotation(self):
        from aos_api.model_provider_credential import get_credential_engine

        engine = get_credential_engine()
        cred = engine.create_credential(
            provider_id="test-rotate",
            api_key="sk-original-key",
        )
        updated = engine.update_credential(
            provider_id="test-rotate",
            key_id=cred.key_id,
            api_key="sk-new-rotated-key",
        )
        assert updated is not None
        assert len(updated.rotation_history) == 1
        assert updated.rotation_history[0].old_key_tail == cred.key_masked

    def test_delete_credential(self):
        from aos_api.model_provider_credential import get_credential_engine

        engine = get_credential_engine()
        cred = engine.create_credential(
            provider_id="test-delete",
            api_key="sk-delete-me",
        )
        assert engine.delete_credential("test-delete", cred.key_id)
        assert not engine.delete_credential("test-delete", cred.key_id)  # Already deleted

    def test_resolve_api_key(self):
        from aos_api.model_provider_credential import get_credential_engine

        engine = get_credential_engine()
        engine.create_credential(
            provider_id="test-resolve",
            api_key="sk-resolvable-key",
        )
        key = engine.resolve_api_key("test-resolve")
        assert key == "sk-resolvable-key"
        assert engine.resolve_api_key("nonexistent") == ""

    def test_rotation_policy_30d(self):
        from aos_api.model_provider_credential import get_credential_engine

        engine = get_credential_engine()
        cred = engine.create_credential(
            provider_id="test-policy",
            api_key="sk-policy-test",
            rotation_policy="30d",
        )
        assert cred.rotation_policy == "30d"
        assert cred.next_rotation_at != ""


# ── Credential API Tests (via TestClient) ─────────────────────


class TestCredentialAPI:
    @pytest.fixture(scope="class")
    def client(self):
        from aos_api.main import create_app

        app = create_app()
        return TestClient(app)

    def test_api_create_credential(self, client):
        resp = client.post(
            "/api/models/providers/test-api-openai/credentials",
            json={"api_key": "sk-api-create-test", "label": "API测试"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "test-api-openai"
        assert data["label"] == "API测试"
        assert "encrypted_key" not in data  # Safety: no raw encrypted key in response

    def test_api_list_credentials(self, client):
        # Create first
        client.post(
            "/api/models/providers/test-api-list/credentials",
            json={"api_key": "sk-list-1"},
        )
        resp = client.get("/api/models/providers/test-api-list/credentials")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    def test_api_update_credential(self, client):
        # Create
        create_resp = client.post(
            "/api/models/providers/test-api-update/credentials",
            json={"api_key": "sk-original", "label": "原标签"},
        )
        key_id = create_resp.json()["key_id"]
        # Update
        resp = client.put(
            f"/api/models/providers/test-api-update/credentials/{key_id}",
            json={"label": "新标签", "rotation_policy": "90d"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] == "新标签"
        assert data["rotation_policy"] == "90d"

    def test_api_delete_credential(self, client):
        # Create
        create_resp = client.post(
            "/api/models/providers/test-api-delete/credentials",
            json={"api_key": "sk-delete-api"},
        )
        key_id = create_resp.json()["key_id"]
        # Delete
        resp = client.delete(
            f"/api/models/providers/test-api-delete/credentials/{key_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        # Delete again → 404
        resp2 = client.delete(
            f"/api/models/providers/test-api-delete/credentials/{key_id}"
        )
        assert resp2.status_code == 404

    def test_api_test_connection_no_key(self, client):
        """Test connection should fail gracefully when no key exists."""
        resp = client.post(
            "/api/models/providers/no-such-provider/test-connection",
            json={},
        )
        # Should return 400 (no API key available)
        assert resp.status_code == 400


# ── Provider Security Tests ───────────────────────────────────


class TestProviderSecurity:
    def test_default_security(self):
        from aos_api.provider_security import get_security_engine

        engine = get_security_engine()
        sec = engine.get_security("test-sec-default")
        assert sec.content_filter is True
        assert sec.max_tokens == 4096
        assert sec.qps_limit == 100
        assert sec.data_residency == "provider"

    def test_update_security(self):
        from aos_api.provider_security import get_security_engine

        engine = get_security_engine()
        sec = engine.update_security(
            "test-sec-update",
            max_tokens=8192,
            qps_limit=200,
            ip_allowlist=["10.0.0.0/8"],
        )
        assert sec.max_tokens == 8192
        assert sec.qps_limit == 200
        assert "10.0.0.0/8" in sec.ip_allowlist

    def test_api_security(self, client):
        # GET default
        resp = client.get("/api/models/providers/test-api-sec/security")
        assert resp.status_code == 200
        assert resp.json()["content_filter"] is True
        # PUT update
        resp = client.put(
            "/api/models/providers/test-api-sec/security",
            json={"max_tokens": 2048, "audit_log": False},
        )
        assert resp.status_code == 200
        assert resp.json()["max_tokens"] == 2048
        assert resp.json()["audit_log"] is False


# ── Call Log Tests ────────────────────────────────────────────


class TestProviderCallLog:
    def test_add_and_list(self):
        from aos_api.provider_call_log import get_call_log_engine

        engine = get_call_log_engine()
        engine.add_log(
            provider_id="test-log",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            latency_ms=800,
            cost_usd=0.002,
            status="success",
        )
        engine.add_log(
            provider_id="test-log",
            model="gpt-4o",
            input_tokens=200,
            output_tokens=100,
            latency_ms=5000,
            cost_usd=0.004,
            status="timeout",
        )
        logs = engine.list_logs("test-log")
        assert len(logs) >= 2
        # Newest first
        assert logs[0].status == "timeout"

    def test_stats(self):
        from aos_api.provider_call_log import get_call_log_engine

        engine = get_call_log_engine()
        engine.add_log(
            provider_id="test-stats",
            input_tokens=100,
            output_tokens=50,
            latency_ms=500,
            cost_usd=0.001,
            status="success",
        )
        stats = engine.get_stats("test-stats")
        assert stats["total_calls"] >= 1
        assert stats["success"] >= 1
        assert stats["total_tokens"] >= 150

    def test_api_logs(self, client):
        # Add a log via engine
        from aos_api.provider_call_log import get_call_log_engine

        engine = get_call_log_engine()
        engine.add_log(
            provider_id="test-api-logs",
            model="gpt-4o",
            status="success",
        )
        resp = client.get("/api/models/providers/test-api-logs/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1
