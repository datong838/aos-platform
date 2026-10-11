"""Recovery successor must preserve source and immutable published coordinates."""
import importlib
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def preparation(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("prepare_ecommerce_qyh_recovery_core_candidate")


def test_successor_preserves_source_and_drops_old_proofs(preparation, tmp_path):
    target = tmp_path / "1.4.3"
    report = preparation.prepare(target)
    assert report["state"] == "UNBUILT_UNSIGNED"
    preparation.validate_candidate(target)
    for source in (preparation.BASE / "backend").rglob("*.py"):
        assert (target / source.relative_to(preparation.BASE)).read_bytes() == source.read_bytes()
    for name in preparation.GENERATED:
        assert not (target / name).exists()
    with pytest.raises(ValueError, match="already exists"):
        preparation.prepare(target)
    (target / "backend/ecommerce_core/__init__.py").write_text("drift")
    with pytest.raises(ValueError, match="candidate.*drifted"):
        preparation.validate_candidate(target)


def test_failed_baseline_leaves_no_candidate(preparation, tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, "BASE_HASH", "0" * 64)
    with pytest.raises(ValueError, match="baseline drifted"):
        preparation.prepare(tmp_path / "1.4.3")
    assert list(tmp_path.iterdir()) == []


def test_unsigned_candidate_rejects_old_proofs_and_symlinks(preparation, tmp_path):
    target = tmp_path / "1.4.3"
    preparation.prepare(target)
    proof = target / "evidence/bundle-evals.json"
    proof.write_text('{"status":"passed","failed":0}')
    with pytest.raises(ValueError, match="candidate.*drifted"):
        preparation.validate_candidate(target)
    proof.unlink()
    (target / "unexpected-link").symlink_to(preparation.BASE / "bundle.yaml")
    with pytest.raises(ValueError, match="symlink drifted"):
        preparation.validate_candidate(target)


def test_recovery_profile_preserves_old_profiles_and_output_boundary(preparation, tmp_path, monkeypatch):
    profile = importlib.import_module("build_ecommerce_qyh_recovery_candidates")
    original = importlib.import_module("build_ecommerce_growth_1_13_candidates")
    old = original.load_builder().preflight()
    builder = profile.load_builder()
    result = builder.preflight()
    assert result["operationCount"] == 15
    assert result["moduleCount"] == 8
    assert {item["id"]: item["version"] for item in result["bundles"]} == {
        "domain.ecommerce.core": "1.4.3", "platform.ecommerce.niushop": "1.23.0",
        "solution.ecommerce.growth": "1.13.0", "solution.ecommerce.operations-base": "1.2.0",
    }
    assert original.load_builder().preflight() == old
    output = tmp_path / "domain.ecommerce.core/1.4.3"
    shutil.copytree(preparation.TARGET, output)
    builder._augment_sbom(output, sdk_hash="a" * 64, base_config_digest="sha256:" + "b" * 64)
    evaluation = json.loads((output / "evidence/bundle-evals.json").read_text())
    assert evaluation["status"] == "passed" and evaluation["failed"] == 0
    assert evaluation["scope"] == "source-preflight-only"
    assert evaluation["runtimeReadiness"] == "unverified"
    assert evaluation["sourceTreeHash"] == builder._tree_hash(preparation.TARGET)
    assert not (preparation.TARGET / "evidence/bundle-evals.json").exists()
    with pytest.raises(ValueError, match="outside candidate source"):
        builder._augment_sbom(preparation.TARGET, sdk_hash="a" * 64,
                              base_config_digest="sha256:" + "b" * 64)
    with pytest.raises(ValueError, match="already exists"):
        builder._augment_sbom(output, sdk_hash="a" * 64, base_config_digest="sha256:" + "b" * 64)
    original_loader = profile._load_growth_builder
    def drifted():
        changed = original_loader()
        changed.ALL_CASES = changed.ALL_CASES[1:]
        return changed
    monkeypatch.setattr(profile, "_load_growth_builder", drifted)
    with pytest.raises(ValueError, match="profile drifted"):
        profile.load_builder()


def test_build_output_drift_rejected_before_evidence(preparation, tmp_path):
    builder = importlib.import_module("build_ecommerce_qyh_recovery_candidates").load_builder()
    output = tmp_path / "domain.ecommerce.core/1.4.3"
    shutil.copytree(preparation.TARGET, output)
    (output / "bundle.yaml").write_text("wrong metadata")
    with pytest.raises(ValueError, match="build source drifted"):
        builder._augment_sbom(output, sdk_hash="a" * 64, base_config_digest="sha256:" + "b" * 64)
    assert not (output / "evidence/bundle-evals.json").exists()
