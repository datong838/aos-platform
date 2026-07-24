"""W1-9 · MediaReference Bridge 单元测试。"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.media_reference import (
    LocalAdapter,
    MediaReferenceError,
    MediaReferenceStore,
    S3MockAdapter,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _new_store() -> MediaReferenceStore:
    return MediaReferenceStore()


# --- 引擎：CRUD --- #

def test_register_and_get():
    s = _new_store()
    ref = s.register("image", "local", "bucket1", "img/a.png", "image/png", 1024)
    assert ref.kind == "image"
    assert s.get(ref.id).bucket == "bucket1"


def test_register_bad_storage():
    s = _new_store()
    with pytest.raises(MediaReferenceError) as exc:
        s.register("image", "ftp", "b", "p")
    assert exc.value.code == "BAD_STORAGE"


def test_register_bad_path():
    s = _new_store()
    with pytest.raises(MediaReferenceError) as exc:
        s.register("image", "local", "", "p")
    assert exc.value.code == "BAD_PATH"


def test_list():
    s = _new_store()
    s.register("image", "local", "b", "p1")
    s.register("video", "local", "b", "p2")
    assert len(s.list_all()) == 2


def test_delete():
    s = _new_store()
    ref = s.register("image", "local", "b", "p")
    s.delete(ref.id)
    with pytest.raises(MediaReferenceError):
        s.get(ref.id)


def test_get_404():
    s = _new_store()
    with pytest.raises(MediaReferenceError) as exc:
        s.get("ghost")
    assert exc.value.code == "NOT_FOUND"


# --- 引擎：签名直链 --- #

def test_signed_url_local():
    s = _new_store()
    ref = s.register("image", "local", "b", "p.png")
    url = s.get_signed_url(ref.id, 1800)
    assert url.startswith("file://")
    assert "expires=" in url


def test_signed_url_s3():
    s = _new_store()
    ref = s.register("image", "s3", "mybucket", "img/a.png")
    url = s.get_signed_url(ref.id)
    assert "s3.mock.local" in url
    assert "X-Amz-Signature" in url


# --- 引擎：缩略图 --- #

def test_generate_thumbnail_image():
    s = _new_store()
    ref = s.register("image", "local", "b", "photo.jpg")
    thumbs = s.generate_thumbnail(ref.id)
    assert "small" in thumbs
    assert "medium" in thumbs
    assert ref.id in thumbs["small"]


def test_generate_thumbnail_video():
    s = _new_store()
    ref = s.register("video", "local", "b", "clip.mp4")
    thumbs = s.generate_thumbnail(ref.id, ["small"])
    assert "small" in thumbs


def test_generate_thumbnail_bad_kind():
    s = _new_store()
    ref = s.register("document", "local", "b", "doc.pdf")
    with pytest.raises(MediaReferenceError) as exc:
        s.generate_thumbnail(ref.id)
    assert exc.value.code == "BAD_KIND"


# --- 引擎：按属主查 --- #

def test_list_by_owner():
    s = _new_store()
    s.register("image", "local", "b", "p1", owner_object_type="WorkOrder", owner_object_id="wo1")
    s.register("image", "local", "b", "p2", owner_object_type="WorkOrder", owner_object_id="wo1")
    s.register("image", "local", "b", "p3", owner_object_type="WorkOrder", owner_object_id="wo2")
    refs = s.list_by_owner("WorkOrder", "wo1")
    assert len(refs) == 2


# --- LocalAdapter --- #

def test_local_adapter_exists(tmp_path):
    adapter = LocalAdapter(str(tmp_path))
    bucket_dir = tmp_path / "bucket1"
    bucket_dir.mkdir()
    (bucket_dir / "a.txt").write_text("hello")
    assert adapter.exists("bucket1", "a.txt") is True
    assert adapter.exists("bucket1", "missing.txt") is False


def test_local_adapter_read_bytes(tmp_path):
    adapter = LocalAdapter(str(tmp_path))
    (tmp_path / "bucket1").mkdir()
    (tmp_path / "bucket1" / "a.txt").write_text("hello world")
    data = adapter.read_bytes("bucket1", "a.txt")
    assert data == b"hello world"


# --- S3MockAdapter --- #

def test_s3_mock_adapter_url():
    adapter = S3MockAdapter()
    url = adapter.signed_url("bucket", "path/to/obj", 900)
    assert "bucket" in url
    assert "Expires=" in url


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = MediaReferenceStore()
    monkeypatch.setattr("aos_api.routers.media_references.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_register(client):
    resp = client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["kind"] == "image"


def test_api_list(client):
    client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H)
    resp = client.get("/v1/media-references", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["media_references"]) == 1


def test_api_get_404(client):
    resp = client.get("/v1/media-references/ghost", headers=_H)
    assert resp.status_code == 404


def test_api_signed_url(client):
    ref_id = client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H).json()["id"]
    resp = client.get(f"/v1/media-references/{ref_id}/signed-url?expires=600", headers=_H)
    assert resp.status_code == 200
    assert "url" in resp.json()


def test_api_thumbnails(client):
    ref_id = client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H).json()["id"]
    resp = client.post(f"/v1/media-references/{ref_id}/thumbnails", json={"sizes": ["small"]}, headers=_H)
    assert resp.status_code == 200
    assert "small" in resp.json()["thumbnails"]


def test_api_by_owner(client):
    client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png",
        "owner_object_type": "WorkOrder", "owner_object_id": "wo1"}, headers=_H)
    resp = client.get("/v1/media-references/by-owner/WorkOrder/wo1", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_api_delete(client):
    ref_id = client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H).json()["id"]
    resp = client.delete(f"/v1/media-references/{ref_id}", headers=_H)
    assert resp.status_code == 200
    assert client.get(f"/v1/media-references/{ref_id}", headers=_H).status_code == 404
