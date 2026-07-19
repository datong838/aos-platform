"""185m — media metadata enrichment (stdlib; no GPU OCR)."""
from __future__ import annotations

import base64
import struct

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.media_meta import extract_metadata
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api import mock_data


def _png_1x1() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_extract_text_and_png_unit():
    meta = extract_metadata(b"a\nb\nc", content_type="text/plain", name="t.txt")
    assert meta["kind"] == "text"
    assert meta["lineCount"] == 3
    assert meta["sha256"]
    assert meta["ocr"] is False
    assert meta["ok"] is True
    png = _png_1x1()
    im = extract_metadata(png, content_type="image/png", name="x.png")
    assert im["kind"] == "image"
    assert im.get("width") == 1
    assert im.get("height") == 1
    assert im["contentTypeSniff"] == "image/png"
    empty = extract_metadata(None, content_type="application/octet-stream")
    assert empty["kind"] == "empty"


@pytest.fixture()
def api(monkeypatch):
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    monkeypatch.setenv("AOS_S3_DISABLED", "1")
    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")
    monkeypatch.setenv("AOS_LITELLM_FALLBACK", "mock")
    app = create_app()
    with TestClient(app) as c:
        yield c


def _h() -> dict[str, str]:
    tok = issue_dev_token(subject="alice", org_id="dev-org", project_id="dev-project")
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_create_media_with_metadata(api):
    raw = b"line1\nline2\n"
    r = api.post(
        "/v1/media-sets",
        headers=_h(),
        json={
            "name": "notes.txt",
            "contentType": "text/plain",
            "bytesBase64": base64.b64encode(raw).decode("ascii"),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metadata"]["kind"] == "text"
    assert body["metadata"]["lineCount"] == 2
    assert body["metadata"]["ocr"] is False
    rid = body["rid"]
    en = api.post(f"/v1/media-sets/{rid}/enrich", headers=_h())
    assert en.status_code == 200
    assert en.json()["metadata"]["byteSize"] == len(raw)


def test_create_png_dimensions(api):
    png = _png_1x1()
    r = api.post(
        "/v1/media-sets",
        headers=_h(),
        json={
            "name": "px.png",
            "contentType": "image/png",
            "bytesBase64": base64.b64encode(png).decode("ascii"),
        },
    )
    assert r.status_code == 200, r.text
    meta = r.json()["metadata"]
    assert meta["width"] == 1 and meta["height"] == 1


def test_png_ihdr_manual():
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = b"IHDR" + struct.pack(">II", 8, 4) + b"\x08\x02\x00\x00\x00"
    chunk = struct.pack(">I", 13) + ihdr + b"\x00\x00\x00\x00"
    data = sig + chunk
    meta = extract_metadata(data, content_type="image/png", name="m.png")
    assert meta["width"] == 8
    assert meta["height"] == 4
