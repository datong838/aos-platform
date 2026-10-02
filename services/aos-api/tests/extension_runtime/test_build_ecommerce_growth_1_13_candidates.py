"""Separate build profile for the unsigned current-backend Growth successor."""
import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("build_ecommerce_growth_1_13_candidates")


def test_profile_selects_only_exact_growth_113(profile):
    builder = profile.load_builder()
    result = builder.preflight()
    assert result["operationCount"] == 15
    assert result["moduleCount"] == 8
    assert {item["id"]: item["version"] for item in result["bundles"]} == {
        "domain.ecommerce.core": "1.4.0",
        "platform.ecommerce.niushop": "1.23.0",
        "solution.ecommerce.growth": "1.13.0",
        "solution.ecommerce.operations-base": "1.2.0",
    }
    old = importlib.import_module("build_ecommerce_growth_1_12_candidates").load_builder()
    assert old.RUNTIME_CASES[2][2] == "1.12.0"


def test_profile_adds_sbom_only_to_build_output(profile, tmp_path, monkeypatch):
    builder = profile.load_builder()
    bundle = tmp_path / "solution.ecommerce.growth" / "1.13.0"
    path = bundle / "evidence/sbom.json"
    path.parent.mkdir(parents=True)
    builder._augment_sbom(bundle, sdk_hash="a" * 64,
                          base_config_digest="sha256:" + "b" * 64)
    names = [item["name"] for item in json.loads(path.read_text())["components"]]
    assert names.count("business-investigation.readonly") == 1
    assert names.count("aos-extension-sdk") == 1
    report = json.loads((bundle / "evidence/bundle-evals.json").read_text())
    assert report["sourceTreeHash"] == profile.SOURCE_TREE_HASH
    assert report["runtimeReadiness"] == "blocked"
    assert (bundle / "evidence/bundle-evals.json").read_bytes() == profile.EVAL_EVIDENCE.read_bytes()
    assert not (ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.13.0/evidence/sbom.json").exists()
    assert not (ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.13.0/evidence/bundle-evals.json").exists()
    path.unlink()
    (bundle / "evidence/bundle-evals.json").unlink()
    monkeypatch.setattr(profile, "BASE_SBOM_HASH", "0" * 64)
    with pytest.raises(ValueError, match="SBOM baseline drifted"):
        builder._augment_sbom(bundle, sdk_hash="a" * 64,
                              base_config_digest="sha256:" + "b" * 64)
    monkeypatch.setattr(profile, "BASE_SBOM_HASH", "ac64aec9f5d0d3535d1174026f3d9ed0bdeb11eef7fd76bb93e220cd1f079d5e")
    monkeypatch.setattr(profile, "EVAL_EVIDENCE_HASH", "0" * 64)
    with pytest.raises(ValueError, match="eval evidence drifted"):
        builder._augment_sbom(bundle, sdk_hash="a" * 64,
                              base_config_digest="sha256:" + "b" * 64)


def test_profile_rejects_source_and_current_profile_drift(profile, monkeypatch):
    reviewed_hash = profile.SOURCE_TREE_HASH
    monkeypatch.setattr(profile, "SOURCE_TREE_HASH", "0" * 64)
    with pytest.raises(ValueError, match="Growth source drifted"):
        profile.load_builder()
    monkeypatch.setattr(profile, "SOURCE_TREE_HASH", reviewed_hash)
    original = profile._load_current_builder
    def changed():
        builder = original()
        builder.EXPECTED_RUNTIME_OPERATION_COUNT = 14
        return builder
    monkeypatch.setattr(profile, "_load_current_builder", changed)
    with pytest.raises(ValueError, match="current profile drifted"):
        profile.load_builder()
