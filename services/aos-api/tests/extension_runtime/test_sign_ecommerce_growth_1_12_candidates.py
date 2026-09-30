"""Isolated local signer for the growth 1.12 build only."""
import importlib
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("sign_ecommerce_growth_1_12_candidates")


@pytest.fixture
def signer(profile):
    return profile.load_signer()


def test_signer_has_separate_profile_and_key_id(signer):
    assert signer.PROFILE.name == "build_ecommerce_growth_1_12_candidates.py"
    assert signer.KEY_ID == "a0v-local-ecommerce-growth-1-12-v1"
    assert {item["id"]: item["version"] for item in signer._builder().preflight()["bundles"]}[
        "solution.ecommerce.growth"] == "1.12.0"


def test_wrong_receipt_rejected_before_state_creation(signer, tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"outcome": "BUILD_GREEN", "output": str(build)}))
    state = tmp_path / "state"
    with pytest.raises(signer.SigningBlocked, match="BUILD_RECEIPT_MISMATCH"):
        signer.validate_build(build=build, receipt_path=receipt, state=state)
    assert not state.exists()


def test_existing_state_is_never_overwritten(signer, tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    sentinel = state / "sentinel"
    sentinel.write_text("keep")
    monkeypatch.setattr(signer, "validate_build", lambda **_: (object(), {}))
    with pytest.raises(signer.SigningBlocked, match="STATE_ALREADY_EXISTS_RECONCILE_READ_ONLY"):
        signer.sign(build=tmp_path, receipt_path=tmp_path, state=state)
    assert sentinel.read_text() == "keep"


def test_qualification_receipt_must_bind_exact_build_and_growth_version(profile, tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    build_receipt = tmp_path / "build-receipt.json"
    build_data = {"outcome": "BUILD_GREEN", "output": str(build),
                  "outputTreeHash": "sha256:" + "a" * 64, "gitHead": "b" * 40,
                  "effects": {"registryPublishCount": 0, "installationMutationCount": 0,
                              "providerInvocationCount": 0, "externalPublicationCount": 0}}
    build_receipt.write_text(json.dumps(build_data))
    qualification_receipt = tmp_path / "qualification.json"
    with pytest.raises(ValueError, match="QUALIFICATION_RECEIPT_REQUIRED"):
        profile.validate_qualification(build=build, build_receipt=build_receipt,
                                       qualification_receipt=qualification_receipt)
    qualification = {"outcome": "QUALIFICATION_GREEN",
                     "buildReceipt": str(build_receipt.resolve()),
                     "buildReceiptHash": "sha256:" + hashlib.sha256(build_receipt.read_bytes()).hexdigest(),
                     "outputTreeHash": build_data["outputTreeHash"],
                     "gitHead": build_data["gitHead"],
                     "effects": build_data["effects"],
                     "resolved": [{"id": "solution.ecommerce.growth", "version": "1.11.0"}],
                     "tamperRejections": ["imageIndexBytes", "imageDigest", "dependencyLock",
                                          "sbom", "backend", "schemaCompatibility", "schemaRequirements"]}
    qualification_receipt.write_text(json.dumps(qualification))
    with pytest.raises(ValueError, match="QUALIFICATION_RECEIPT_MISMATCH"):
        profile.validate_qualification(build=build, build_receipt=build_receipt,
                                       qualification_receipt=qualification_receipt)
    qualification["resolved"][0]["version"] = "1.12.0"
    qualification_receipt.write_text(json.dumps(qualification))
    assert profile.validate_qualification(build=build, build_receipt=build_receipt,
                                          qualification_receipt=qualification_receipt) is None
