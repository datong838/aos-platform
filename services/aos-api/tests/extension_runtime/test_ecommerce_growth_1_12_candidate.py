"""Immutable BI template successor candidate; no signed-release claim."""
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

import pytest

from aos_api.aip_business_investigation_responsibility_template import BIResponsibilityTemplate
from aos_api.asset_registry.manifest_loader import ManifestLoader


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/prepare_ecommerce_growth_1_12_candidate.py"
BASE = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0"
TARGET = BASE.parent / "1.12.0"
TEMPLATE = "content/responsibility-templates/business-investigation.readonly.json"


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("growth_1_12_prepare", SCRIPT)
        value = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(value)
        return value
    finally:
        sys.path.remove(str(SCRIPT.parent))


def test_new_candidate_has_exact_bi_template_without_old_approval_artifacts():
    source = module()
    assert source.tree_hash(BASE) == source.BASE_HASH
    assert TARGET.is_dir()
    manifest = (TARGET / "bundle.yaml").read_text()
    assert "  version: 1.12.0\n" in manifest
    assert "      - content/responsibility-templates/\n" in manifest
    payload = json.loads((TARGET / TEMPLATE).read_text())
    BIResponsibilityTemplate.model_validate(payload)
    assert len(payload["slots"]) == 6
    assert all("assignee" not in slot for slot in payload["slots"])
    assert not (TARGET / "bundle.signature.json").exists()
    evaluation = json.loads((TARGET / "evidence/bundle-evals.json").read_text())
    assert evaluation["status"] == "passed" and evaluation["failed"] == 0
    assert evaluation["runtimeReadiness"] == "blocked"
    assert not (TARGET / "artifacts/runtime-image-index.json").exists()
    assert not (TARGET / "artifacts/python-dependencies.lock").exists()
    provenance = json.loads((TARGET / "evidence/content-source-provenance.json").read_text())
    assert provenance["status"] == "UNBUILT_UNSIGNED"
    assert provenance["baseTreeHash"] == source.BASE_HASH
    assert provenance["biTemplateSha256"] == "sha256:" + hashlib.sha256(
        (TARGET / TEMPLATE).read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="already exists"):
        source.prepare()


def test_new_candidate_rewrites_only_its_own_version_refs():
    source = module()
    loaded = ManifestLoader({"candidate": BASE.parent}).load("bundle://candidate/1.12.0")
    assert loaded.manifest.metadata.version == "1.12.0"
    assert source.tree_hash(BASE) == source.BASE_HASH
    for path in (TARGET / "content/workshops").glob("*.json"):
        raw = path.read_text()
        assert "bundle://aos/solution.ecommerce.growth@1.11.0" not in raw
        if "bundleRef" in raw:
            assert "bundle://aos/solution.ecommerce.growth@1.12.0" in raw


def test_prepare_rejects_drift_without_partial_target(tmp_path, monkeypatch):
    source = module()
    monkeypatch.setattr(source, "BASE_HASH", "0" * 64)
    target = tmp_path / "1.12.0"
    with pytest.raises(ValueError, match="baseline drifted"):
        source.prepare(target)
    assert not target.exists()
