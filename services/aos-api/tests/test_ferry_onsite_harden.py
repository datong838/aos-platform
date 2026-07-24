"""Ferry onsite harden — scheme 162 (no Docker required)."""
from __future__ import annotations

import json

import pytest

from aos_api import ferry
from aos_api.errors import ApiError


def _onsite_body(*, secret: str | None = None) -> tuple[bytes, str]:
    doc = {
        "version": "1",
        "skopeoUsed": False,
        "onsitePack": True,
        "cosignMode": "cosign-dev-hmac",
        "images": [
            {
                "ref": "alpine:latest",
                "digest": "sha256:" + ("a" * 64),
                "digestSource": "synthetic",
                "archive": None,
            }
        ],
    }
    body = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
    if secret is not None:
        import hashlib
        import hmac as hm

        sig = hm.new(secret.encode(), b"ferry-images:" + body, hashlib.sha256).hexdigest()
    else:
        sig = ferry._sign_images_dev(body)
    return body, sig


def test_archive_exceeds_max_gib():
    assert ferry.archive_exceeds_max_gib(0, 1.0) is False
    assert ferry.archive_exceeds_max_gib(100, 0) is False
    assert ferry.archive_exceeds_max_gib(1024**3, 1.0) is False
    assert ferry.archive_exceeds_max_gib(1024**3 + 1, 1.0) is True
    assert ferry.archive_exceeds_max_gib(5 * 1024**3, 2.5) is True


def test_onsite_hmac_matches_verify_images_layer(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_HMAC_SECRET", "unit-test-ferry-hmac")
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    body, sig = _onsite_body()
    members = ferry.onsite_images_members(body, sig)
    doc = ferry._verify_images_layer(members)
    assert doc["onsitePack"] is True
    assert doc["cosignMode"] == "cosign-dev-hmac"
    assert doc["images"][0]["ref"] == "alpine:latest"


def test_onsite_hmac_mismatch_rejected(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_HMAC_SECRET", "unit-test-ferry-hmac")
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    body, _sig = _onsite_body()
    members = ferry.onsite_images_members(body, "deadbeef" * 8)
    with pytest.raises(ApiError) as ei:
        ferry._verify_images_layer(members)
    assert ei.value.code == "FERRY_IMAGE_SIGNATURE_INVALID"


def test_onsite_cosign_required_rejects_hmac(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_HMAC_SECRET", "unit-test-ferry-hmac")
    monkeypatch.setenv("AOS_FERRY_COSIGN_REQUIRED", "1")
    body, sig = _onsite_body()
    members = ferry.onsite_images_members(body, sig)
    with pytest.raises(ApiError) as ei:
        ferry._verify_images_layer(members)
    assert ei.value.code == "FERRY_COSIGN_REQUIRED"
    assert ei.value.status_code == 403


def test_onsite_pack_script_hmac_contract(tmp_path, monkeypatch):
    """Simulate pack-ferry-images-onsite.sh HMAC bytes (same formula as script)."""
    import hashlib
    import hmac as hm

    secret = "pack-script-secret"
    monkeypatch.setenv("AOS_FERRY_HMAC_SECRET", secret)
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)

    images_doc = {
        "version": "1",
        "skopeoUsed": False,
        "onsitePack": True,
        "cosignMode": "cosign-dev-hmac",
        "images": [],
    }
    body = json.dumps(images_doc, indent=2, ensure_ascii=False).encode("utf-8")
    (tmp_path / "images.json").write_bytes(body)
    sig = hm.new(secret.encode(), b"ferry-images:" + body, hashlib.sha256).hexdigest()
    (tmp_path / "images.sig").write_text(sig, encoding="ascii")

    loaded = (tmp_path / "images.json").read_bytes()
    loaded_sig = (tmp_path / "images.sig").read_text(encoding="ascii").strip()
    assert ferry._verify_images_dev(loaded, loaded_sig)
    doc = ferry._verify_images_layer(ferry.onsite_images_members(loaded, loaded_sig))
    assert doc["onsitePack"] is True


def test_status_plan_ref_mentions_162(monkeypatch):
    monkeypatch.delenv("AOS_FERRY_COSIGN_REQUIRED", raising=False)
    st = ferry.ferry_status_payload()
    assert "162" in st["planRef"]
    assert "62" in st["message"] or "onsite" in st["message"].lower()
