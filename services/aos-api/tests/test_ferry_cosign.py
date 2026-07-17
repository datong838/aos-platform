"""Ferry cosign keychain — scheme 64 (mocked CLI; no real cosign required)."""
from __future__ import annotations

import base64

import pytest

from aos_api import ferry
from aos_api.errors import ApiError


def test_status_full_channel_deferred(monkeypatch):
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    st = ferry.ferry_status_payload()
    assert st["fullChannelDeferred"] is True
    assert "lite" in st["channels"]
    assert "cosignRequired" in st
    assert "cosignCliMode" in st
    assert "64" in st["planRef"]


def test_hmac_still_works_without_keys(monkeypatch):
    monkeypatch.delenv("AOS_FERRY_COSIGN_KEY", raising=False)
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "0")
    _b, _s, doc, _e = ferry.build_images_artifact()
    assert doc["cosignMode"] == "cosign-dev-hmac"


def test_required_without_key_raises(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_COSIGN_REQUIRED", "1")
    monkeypatch.delenv("AOS_FERRY_COSIGN_KEY", raising=False)
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "0")
    with pytest.raises(ApiError) as ei:
        ferry.build_images_artifact()
    assert ei.value.code == "FERRY_COSIGN_REQUIRED"
    assert ei.value.status_code == 503


def test_mock_cosign_sign_path(monkeypatch, tmp_path):
    key = tmp_path / "cosign.key"
    key.write_text("dummy", encoding="utf-8")
    monkeypatch.setenv("AOS_FERRY_COSIGN_KEY", str(key))
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "0")
    monkeypatch.setattr(ferry, "cosign_cli_mode", lambda: "path")

    def _fake_sign(data: bytes):
        return base64.b64encode(b"SIG-" + data[:8]).decode("ascii"), "cosign"

    monkeypatch.setattr(ferry, "_cosign_sign_blob", _fake_sign)
    _b, sig, doc, _e = ferry.build_images_artifact()
    assert doc["cosignMode"] == "cosign"
    assert sig.startswith(b"U0lH") or b"SIG" in base64.b64decode(sig.strip())


def test_import_rejects_hmac_when_required(monkeypatch, client, auth_headers):
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "0")
    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    assert ex.status_code == 200
    assert ex.json()["images"]["cosignMode"] == "cosign-dev-hmac"

    monkeypatch.setenv("AOS_FERRY_COSIGN_REQUIRED", "1")
    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": ex.json()["contentBase64"]},
    )
    assert im.status_code == 403
    assert im.json()["code"] == "FERRY_COSIGN_REQUIRED"


def test_export_required_503(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_FERRY_COSIGN_REQUIRED", "1")
    monkeypatch.delenv("AOS_FERRY_COSIGN_KEY", raising=False)
    r = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    assert r.status_code == 503
    assert r.json()["code"] == "FERRY_COSIGN_REQUIRED"
