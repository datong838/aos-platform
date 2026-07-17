import base64
import os

import pytest

from aos_api.object_store import get_config, health_probe, object_key_for


def test_object_key_sanitizes():
    k = object_key_for("ri.mediaset.abc", "a b/c?.bin")
    assert k.startswith("mediasets/ri.mediaset.abc/")
    assert " " not in k


def test_create_media_metadata_only_without_store(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_S3_DISABLED", "1")
    r = client.post(
        "/v1/media-sets",
        headers=auth_headers,
        json={"name": "x.bin", "bytesBase64": base64.b64encode(b"hello").decode()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rid"]
    assert body.get("stored") is False
    assert body["objectStore"] == "metadata-only"
    assert "aos_dev_only_change_me" not in str(body)


def test_object_store_health_no_secret_leak(client, auth_headers):
    r = client.get("/v1/object-store/health", headers=auth_headers)
    assert r.status_code == 200
    blob = r.text
    assert "aos_dev_only_change_me" not in blob
    assert "accessKeyRef" in r.json() or "detail" in r.json() or "ok" in r.json()


@pytest.mark.skipif(
    os.environ.get("AOS_S3_LIVE") != "1",
    reason="set AOS_S3_LIVE=1 for live MinIO roundtrip",
)
def test_live_minio_roundtrip():
    probe = health_probe()
    assert probe.get("ok") is True
    assert probe.get("roundTrip") is True
