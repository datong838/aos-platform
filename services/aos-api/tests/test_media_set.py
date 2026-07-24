"""W1-16 · MediaSet 类型化 + 表格行变换 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.media_reference import MediaReferenceStore
from aos_api.media_set import MediaSetError, MediaSetStore

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _setup(monkeypatch):
    media_store = MediaReferenceStore()
    ms_store = MediaSetStore()
    monkeypatch.setattr("aos_api.media_set.get_media_store", lambda: media_store)
    return media_store, ms_store


# --- 引擎：CRUD --- #

def test_create_image_set():
    ms_store = MediaSetStore()
    ms = ms_store.create("images", "image")
    assert ms.type == "image"
    assert any(f.name == "media_ref_id" for f in ms.schema)


def test_create_bad_type():
    ms_store = MediaSetStore()
    with pytest.raises(MediaSetError) as exc:
        ms_store.create("x", "bogus")
    assert exc.value.code == "BAD_TYPE"


def test_get_404(monkeypatch):
    _, ms_store = _setup(monkeypatch)
    with pytest.raises(MediaSetError) as exc:
        ms_store.get("ghost")
    assert exc.value.code == "NOT_FOUND"


def test_list(monkeypatch):
    _, ms_store = _setup(monkeypatch)
    ms_store.create("a", "image")
    ms_store.create("b", "audio")
    assert len(ms_store.list_all()) == 2


def test_delete(monkeypatch):
    _, ms_store = _setup(monkeypatch)
    ms = ms_store.create("a", "image")
    ms_store.delete(ms.id)
    with pytest.raises(MediaSetError):
        ms_store.get(ms.id)


# --- 引擎：add/remove media --- #

def test_add_media_type_match(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    ref = media_store.register("image", "local", "b", "p.png", size_bytes=1024)
    ms = ms_store.create("imgs", "image")
    ms_store.add_media(ms.id, ref.id)
    assert ref.id in ms_store.get(ms.id).media_ref_ids


def test_add_media_type_mismatch(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    ref = media_store.register("audio", "local", "b", "a.mp3")
    ms = ms_store.create("imgs", "image")
    with pytest.raises(MediaSetError) as exc:
        ms_store.add_media(ms.id, ref.id)
    assert exc.value.code == "TYPE_MISMATCH"


def test_add_media_dicom_accepts_image(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    ref = media_store.register("image", "local", "b", "scan.dcm")
    ms = ms_store.create("scans", "dicom")
    ms_store.add_media(ms.id, ref.id)
    assert ref.id in ms.media_ref_ids


def test_add_media_not_found(monkeypatch):
    _, ms_store = _setup(monkeypatch)
    ms = ms_store.create("imgs", "image")
    with pytest.raises(MediaSetError) as exc:
        ms_store.add_media(ms.id, "ghost-ref")
    assert exc.value.code == "MEDIA_NOT_FOUND"


def test_add_media_idempotent(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    ref = media_store.register("image", "local", "b", "p.png")
    ms = ms_store.create("imgs", "image")
    ms_store.add_media(ms.id, ref.id)
    ms_store.add_media(ms.id, ref.id)
    assert ms_store.get(ms.id).media_ref_ids.count(ref.id) == 1


def test_remove_media(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    ref = media_store.register("image", "local", "b", "p.png")
    ms = ms_store.create("imgs", "image")
    ms_store.add_media(ms.id, ref.id)
    ms_store.remove_media(ms.id, ref.id)
    assert ref.id not in ms_store.get(ms.id).media_ref_ids


def test_remove_media_not_in_set(monkeypatch):
    _, ms_store = _setup(monkeypatch)
    ms = ms_store.create("imgs", "image")
    with pytest.raises(MediaSetError):
        ms_store.remove_media(ms.id, "ghost")


# --- 引擎：rows + transform --- #

def test_get_rows(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    r1 = media_store.register("image", "local", "b", "p1.png", size_bytes=100)
    r2 = media_store.register("image", "local", "b", "p2.png", size_bytes=200)
    ms = ms_store.create("imgs", "image")
    ms_store.add_media(ms.id, r1.id)
    ms_store.add_media(ms.id, r2.id)
    rows = ms_store.get_rows(ms.id)
    assert len(rows) == 2
    assert rows[0]["size_bytes"] == 100


def test_transform_sort(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    r1 = media_store.register("image", "local", "b", "p1.png", size_bytes=100)
    r2 = media_store.register("image", "local", "b", "p2.png", size_bytes=300)
    r3 = media_store.register("image", "local", "b", "p3.png", size_bytes=200)
    ms = ms_store.create("imgs", "image")
    for r in [r1, r2, r3]:
        ms_store.add_media(ms.id, r.id)
    rows = ms_store.transform(ms.id, "sort", {"field": "size_bytes", "descending": True})
    assert rows[0]["size_bytes"] == 300
    assert rows[2]["size_bytes"] == 100


def test_transform_filter(monkeypatch):
    media_store, ms_store = _setup(monkeypatch)
    r1 = media_store.register("image", "local", "b", "p1.png", size_bytes=100)
    r2 = media_store.register("image", "local", "b", "p2.png", size_bytes=300)
    ms = ms_store.create("imgs", "image")
    ms_store.add_media(ms.id, r1.id)
    ms_store.add_media(ms.id, r2.id)
    rows = ms_store.transform(ms.id, "filter", {"expression": "size_bytes > 200"})
    assert len(rows) == 1


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    media_store = MediaReferenceStore()
    ms_store = MediaSetStore()
    monkeypatch.setattr("aos_api.routers.media_sets.get_store", lambda: ms_store)
    monkeypatch.setattr("aos_api.routers.media_references.get_store", lambda: media_store)
    monkeypatch.setattr("aos_api.media_set.get_media_store", lambda: media_store)
    return TestClient(create_app())


def test_api_create(client):
    resp = client.post("/v1/media-set-builder", json={"name": "imgs", "type": "image"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["type"] == "image"


def test_api_add_media(client):
    ms_id = client.post("/v1/media-set-builder", json={"name": "imgs", "type": "image"}, headers=_H).json()["id"]
    ref_id = client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H).json()["id"]
    resp = client.post(f"/v1/media-set-builder/{ms_id}/media", json={"media_ref_id": ref_id}, headers=_H)
    assert resp.status_code == 200
    assert ref_id in resp.json()["media_ref_ids"]


def test_api_rows(client):
    ms_id = client.post("/v1/media-set-builder", json={"name": "imgs", "type": "image"}, headers=_H).json()["id"]
    resp = client.get(f"/v1/media-set-builder/{ms_id}/rows", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_api_transform(client):
    ms_id = client.post("/v1/media-set-builder", json={"name": "imgs", "type": "image"}, headers=_H).json()["id"]
    for i in range(3):
        client.post("/v1/media-references", json={
            "kind": "image", "storage": "local", "bucket": "b",
            "path": f"p{i}.png", "size_bytes": (i + 1) * 100}, headers=_H)
        ref_id = client.get("/v1/media-references", headers=_H).json()["media_references"][-1]["id"]
        client.post(f"/v1/media-set-builder/{ms_id}/media", json={"media_ref_id": ref_id}, headers=_H)
    resp = client.post(f"/v1/media-set-builder/{ms_id}/transform", json={
        "op": "sort", "config": {"field": "size_bytes", "descending": True}}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["rows"][0]["size_bytes"] == 300


def test_api_get_404(client):
    resp = client.get("/v1/media-set-builder/ghost", headers=_H)
    assert resp.status_code == 404


def test_api_delete(client):
    ms_id = client.post("/v1/media-set-builder", json={"name": "imgs", "type": "image"}, headers=_H).json()["id"]
    resp = client.delete(f"/v1/media-set-builder/{ms_id}", headers=_H)
    assert resp.status_code == 200


def test_api_type_mismatch(client):
    ms_id = client.post("/v1/media-set-builder", json={"name": "imgs", "type": "audio"}, headers=_H).json()["id"]
    ref_id = client.post("/v1/media-references", json={
        "kind": "image", "storage": "local", "bucket": "b", "path": "p.png"}, headers=_H).json()["id"]
    resp = client.post(f"/v1/media-set-builder/{ms_id}/media", json={"media_ref_id": ref_id}, headers=_H)
    assert resp.status_code == 400
