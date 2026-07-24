"""Ferry skopeo archive — scheme 59 (mocked; no live docker required)."""
from __future__ import annotations

import base64
import io
import tarfile

from aos_api import ferry


def test_status_reports_skopeo_mode(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "0")
    monkeypatch.setattr(ferry, "skopeo_mode", lambda: "docker")
    st = ferry.ferry_status_payload()
    assert st["skopeo"] is True
    assert st["skopeoMode"] == "docker"
    assert st["skopeoArchiveEnabled"] is False
    assert "alpine:latest" in st["skopeoRefs"]


def test_skopeo_archive_embedded_when_enabled(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "1")
    monkeypatch.setenv("AOS_FERRY_SKOPEO_REFS", "alpine:latest")
    monkeypatch.setenv("AOS_FERRY_IMAGES", "alpine:latest")
    monkeypatch.setattr(ferry, "skopeo_mode", lambda: "docker")
    monkeypatch.setattr(ferry, "probe_docker", lambda: True)

    fake_tar = b"FAKE-DOCKER-ARCHIVE-BYTES"

    def _fake_copy_docker(ref: str, dest_file: str) -> bool:
        assert ref == "alpine:latest"
        with open(dest_file, "wb") as f:
            f.write(fake_tar)
        return True

    monkeypatch.setattr(ferry, "_skopeo_copy_docker", _fake_copy_docker)
    monkeypatch.setattr(ferry, "_skopeo_copy_path", lambda *_a, **_k: False)

    images_bytes, _sig, doc, extra = ferry.build_images_artifact()
    assert doc["skopeoUsed"] is True
    entry = next(i for i in doc["images"] if i["ref"] == "alpine:latest")
    assert entry["archive"]
    assert entry["archive"] in extra
    assert extra[entry["archive"]] == fake_tar
    assert b"alpine" in images_bytes or b"skopeoUsed" in images_bytes


def test_export_includes_archive_member(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "1")
    monkeypatch.setenv("AOS_FERRY_SKOPEO_REFS", "alpine:latest")
    monkeypatch.setenv("AOS_FERRY_IMAGES", "alpine:latest")
    monkeypatch.setattr(ferry, "skopeo_mode", lambda: "docker")

    def _fake_copy_docker(ref: str, dest_file: str) -> bool:
        with open(dest_file, "wb") as f:
            f.write(b"ARCHIVE")
        return True

    monkeypatch.setattr(ferry, "_skopeo_copy_docker", _fake_copy_docker)
    monkeypatch.setattr(ferry, "_skopeo_copy_path", lambda *_a, **_k: False)

    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    assert ex.status_code == 200
    raw = base64.b64decode(ex.json()["contentBase64"])
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        names = {m.name for m in tar.getmembers() if m.isfile()}
    assert any(n.startswith("artifacts/archives/") and n.endswith(".tar") for n in names)


def test_skopeo_off_no_archive(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "0")
    monkeypatch.setenv("AOS_FERRY_IMAGES", "alpine:latest")
    _b, _s, doc, extra = ferry.build_images_artifact()
    assert doc["skopeoUsed"] is False
    assert not any(k.startswith("artifacts/archives/") for k in extra)
