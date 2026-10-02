"""Unsigned successor must preserve 1.12 while carrying today's Growth backend."""
from __future__ import annotations

import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from aos_api.asset_registry.manifest_loader import ManifestLoader


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/prepare_ecommerce_growth_1_13_candidate.py"
BASE = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.12.0"
TARGET = BASE.parent / "1.13.0"
CURRENT = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth"
PACKAGE = "backend/ecommerce_growth"


def _source():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("growth_113_prepare", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT.parent))


def test_immutable_unsigned_successor_contains_only_reviewed_backend_delta():
    source = _source()
    assert source.tree_hash(BASE) == source.BASE_HASH
    assert TARGET.is_dir()
    loaded = ManifestLoader({"candidate": BASE.parent}).load("bundle://candidate/1.13.0")
    assert loaded.manifest.metadata.version == "1.13.0"
    assert len([item for item in loaded.manifest.spec.contributions
                if item.kind == "api" and item.operation_id.startswith("ecommerce_growth_")]) == 10
    assert len([item for item in loaded.manifest.spec.contributions
                if item.kind == "api"]) == 11
    backend = TARGET / PACKAGE
    base_backend = BASE / PACKAGE
    assert {p.name for p in backend.glob("*.py")} == {p.name for p in CURRENT.glob("*.py")}
    for path in CURRENT.glob("*.py"):
        expected = CURRENT if path.name in source.BACKEND_DELTA else base_backend
        assert sha256((backend / path.name).read_bytes()).digest() == sha256(
            (expected / path.name).read_bytes()).digest()
    for name in source.BACKEND_DELTA:
        assert (backend / name).read_bytes() == (CURRENT / name).read_bytes()
    assert not (TARGET / "bundle.signature.json").exists()
    assert not (TARGET / "artifacts/runtime-image-index.json").exists()
    assert not (TARGET / "artifacts/python-dependencies.lock").exists()
    assert not (TARGET / "evidence/bundle-evals.json").exists()
    assert not (TARGET / "evidence/sbom.json").exists()
    provenance = json.loads((TARGET / "evidence/content-source-provenance.json").read_text())
    assert provenance["status"] == "UNBUILT_UNSIGNED"
    assert provenance["baseTreeHash"] == source.BASE_HASH
    assert provenance["backendSourceSha256"] == source.BACKEND_DELTA
    workshop_refs = [p.read_text() for p in (TARGET / "content/workshops").glob("*.json")]
    assert sum("bundle://aos/solution.ecommerce.growth@1.13.0" in raw for raw in workshop_refs) == 8
    assert all("bundle://aos/solution.ecommerce.growth@1.12.0" not in raw for raw in workshop_refs)
    with pytest.raises(ValueError, match="already exists"):
        source.prepare()


def test_successor_manifest_registration_and_schema_match_original_builder():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from build_ecommerce_runtime_candidates import (
            _load_manifest, _manifest_api_registration, _runtime_registration,
            _schema_compatibility,
        )
        assert _runtime_registration(TARGET, "ecommerce_growth") == _manifest_api_registration(
            _load_manifest(TARGET))
        assert len(_runtime_registration(TARGET, "ecommerce_growth")) == 11
        compatibility = _schema_compatibility(TARGET, "solution.ecommerce.growth")
        assert compatibility.startswith("sha256:") and len(compatibility) == 71
    finally:
        sys.path.remove(str(ROOT / "scripts"))


def test_successor_rejects_drift_without_partial_target(tmp_path, monkeypatch):
    source = _source()
    monkeypatch.setattr(source, "BASE_HASH", "0" * 64)
    target = tmp_path / "1.13.0"
    with pytest.raises(ValueError, match="baseline drifted"):
        source.prepare(target)
    assert not target.exists()
    monkeypatch.setattr(source, "BASE_HASH", source.tree_hash(BASE))
    monkeypatch.setitem(source.BACKEND_DELTA, "__init__.py", "0" * 64)
    with pytest.raises(ValueError, match="backend delta drifted"):
        source.prepare(target)
    assert not target.exists()
