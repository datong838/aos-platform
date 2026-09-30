"""Separate growth 1.12 build profile; current profile remains frozen."""
import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("build_ecommerce_growth_1_12_candidates")


def test_new_profile_selects_only_growth_successor(profile):
    builder = profile.load_builder()
    result = builder.preflight()
    assert result["operationCount"] == 15
    assert {item["id"]: item["version"] for item in result["bundles"]} == {
        "domain.ecommerce.core": "1.4.0",
        "platform.ecommerce.niushop": "1.23.0",
        "solution.ecommerce.growth": "1.12.0",
        "solution.ecommerce.operations-base": "1.2.0",
    }
    current = importlib.import_module("build_ecommerce_current_candidates").load_builder()
    assert current.RUNTIME_CASES[2][2] == "1.11.0"


def test_new_profile_builds_fresh_growth_sbom_only_in_output(profile, tmp_path, monkeypatch):
    builder = profile.load_builder()
    bundle = tmp_path / "solution.ecommerce.growth" / "1.12.0"
    path = bundle / "evidence/sbom.json"
    path.parent.mkdir(parents=True)
    builder._augment_sbom(bundle, sdk_hash="a" * 64, base_config_digest="sha256:" + "b" * 64)
    document = json.loads(path.read_text())
    names = [component["name"] for component in document["components"]]
    assert names.count("business-investigation.readonly") == 1
    assert "aos-extension-sdk" in names
    assert not (ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.12.0/evidence/sbom.json").exists()
    monkeypatch.setattr(profile, "BASE_SBOM_HASH", "0" * 64)
    with pytest.raises(ValueError, match="SBOM baseline drifted"):
        builder._augment_sbom(bundle, sdk_hash="a" * 64, base_config_digest="sha256:" + "b" * 64)


def test_new_profile_rejects_current_case_drift(profile, monkeypatch):
    original = profile._load_current_builder
    def changed():
        builder = original()
        builder.EXPECTED_RUNTIME_OPERATION_COUNT = 14
        return builder
    monkeypatch.setattr(profile, "_load_current_builder", changed)
    with pytest.raises(ValueError, match="current profile drifted"):
        profile.load_builder()
