import base64
import os
import urllib.error

import pytest

from aos_api.object_store import _aws4_request, get_config, health_probe, object_key_for


def test_object_key_sanitizes():
    k = object_key_for(
        "ri.mediaset.abc",
        "a b/c?.bin",
        org_id="dev-org",
        project_id="dev-project",
    )
    assert k.startswith("dev-org/dev-project/mediasets/ri.mediaset.abc/")
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


def test_aws4_request_bounds_get_response_before_reading_all(monkeypatch):
    seen = []

    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, count=-1):
            seen.append(count)
            return b"12345"[:count]

    monkeypatch.setattr("urllib.request.urlopen", lambda _req, timeout: Response())
    with pytest.raises(RuntimeError, match="s3_object_too_large"):
        _aws4_request(method="GET", url="http://127.0.0.1:9000/bucket/key",
                      host="127.0.0.1:9000", path="/bucket/key", body=b"",
                      access_key="test", secret_key="test", region="us-east-1",
                      max_response_bytes=3)
    assert seen == [4]


def test_aws4_request_bounds_error_body(monkeypatch):
    seen = []

    class Error(urllib.error.HTTPError):
        def read(self, count=-1):
            seen.append(count)
            return b"error"[:count]

    def raise_http(_req, timeout):
        raise Error("http://127.0.0.1:9000/bucket/key", 404, "missing", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", raise_http)
    with pytest.raises(RuntimeError, match="s3_http_404"):
        _aws4_request(method="GET", url="http://127.0.0.1:9000/bucket/key",
                      host="127.0.0.1:9000", path="/bucket/key", body=b"",
                      access_key="test", secret_key="test", region="us-east-1",
                      max_response_bytes=3)
    assert seen == [200]


@pytest.mark.skipif(
    os.environ.get("AOS_S3_LIVE") != "1",
    reason="set AOS_S3_LIVE=1 for live MinIO roundtrip",
)
def test_live_minio_roundtrip():
    probe = health_probe()
    assert probe.get("ok") is True
    assert probe.get("roundTrip") is True
