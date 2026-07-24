"""Ferry onsite large-image helpers — scheme 62."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_api import ferry


def test_refs_from_manifest():
    doc = {
        "version": "1",
        "images": [
            {"ref": "alpine:latest", "archive": True, "maxGiB": 1},
            {"ref": "postgres:16-alpine", "archive": False},
            {"ref": "alpine:latest", "archive": True},
        ],
    }
    all_refs, arch = ferry.refs_from_manifest(doc)
    assert all_refs == ["alpine:latest", "postgres:16-alpine"]
    assert arch == ["alpine:latest"]


def test_load_manifest_file(tmp_path, monkeypatch):
    p = tmp_path / "cust.json"
    p.write_text(
        json.dumps(
            {
                "version": "1",
                "images": [
                    {"ref": "busybox:latest", "archive": True},
                    {"ref": "hello:1", "archive": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AOS_FERRY_IMAGES_MANIFEST", str(p))
    monkeypatch.delenv("AOS_FERRY_IMAGES", raising=False)
    monkeypatch.delenv("AOS_FERRY_SKOPEO_REFS", raising=False)
    assert ferry._image_refs() == ["busybox:latest", "hello:1"]
    assert ferry._skopeo_refs() == ["busybox:latest"]


def test_max_embed_skips_large_archive(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_SKOPEO", "1")
    monkeypatch.setenv("AOS_FERRY_SKOPEO_REFS", "alpine:latest")
    monkeypatch.setenv("AOS_FERRY_IMAGES", "alpine:latest")
    monkeypatch.setenv("AOS_FERRY_SKOPEO_MAX_MIB", "1")  # 1 MiB
    monkeypatch.setattr(ferry, "skopeo_mode", lambda: "docker")
    monkeypatch.setattr(ferry, "probe_docker", lambda: True)

    big = b"X" * (2 * 1024 * 1024)

    def _fake_copy_docker(ref: str, dest_file: str) -> bool:
        with open(dest_file, "wb") as f:
            f.write(big)
        return True

    monkeypatch.setattr(ferry, "_skopeo_copy_docker", _fake_copy_docker)
    monkeypatch.setattr(ferry, "_skopeo_copy_path", lambda *_a, **_k: False)

    _b, _s, doc, extra = ferry.build_images_artifact()
    assert doc["skopeoUsed"] is False
    assert not any(k.startswith("artifacts/archives/") for k in extra)
    entry = next(i for i in doc["images"] if i["ref"] == "alpine:latest")
    assert entry["archive"] is None


def test_skopeo_timeout_env(monkeypatch):
    monkeypatch.setenv("AOS_FERRY_SKOPEO_TIMEOUT", "120")
    assert ferry._skopeo_timeout("path") == 120
    assert ferry._skopeo_timeout("docker") == 120


def test_example_manifest_on_disk():
    root = Path(__file__).resolve().parents[3]
    p = root / "deploy" / "ferry" / "customer-images.example.json"
    assert p.is_file()
    doc = json.loads(p.read_text(encoding="utf-8"))
    all_refs, arch = ferry.refs_from_manifest(doc)
    assert "alpine:latest" in all_refs
    assert "alpine:latest" in arch
    assert "postgres:16-alpine" in all_refs


def test_status_includes_scheme62_fields(monkeypatch):
    monkeypatch.delenv("AOS_FERRY_IMAGES_MANIFEST", raising=False)
    st = ferry.ferry_status_payload()
    assert "skopeoMaxEmbedMiB" in st
    assert "skopeoTimeoutSec" in st
    assert "62" in st["planRef"]
