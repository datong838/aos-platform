"""Isolated local Growth 1.13 signer requires the exact qualification receipt."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
EFFECTS = {"registryPublishCount": 0, "installationMutationCount": 0,
           "providerInvocationCount": 0, "externalPublicationCount": 0}
VERSIONS = {"domain.ecommerce.core": "1.4.0",
            "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.13.0",
            "solution.ecommerce.operations-base": "1.2.0"}


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("sign_ecommerce_growth_1_13_candidates")


def test_signer_uses_distinct_growth_profile_and_key(profile):
    signer = profile.load_signer()
    assert signer.PROFILE.name == "build_ecommerce_growth_1_13_candidates.py"
    assert signer.KEY_ID == "a0v-local-ecommerce-growth-1-13-v1"
    assert {item["id"]: item["version"] for item in signer._builder().preflight()["bundles"]} == VERSIONS
    old = importlib.import_module("sign_ecommerce_growth_1_12_candidates").load_signer()
    assert old.KEY_ID == "a0v-local-ecommerce-growth-1-12-v1"


def test_qualification_requires_exact_build_and_runtime_evidence(profile, tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    build_receipt = tmp_path / "build-receipt.json"
    build_data = {"outcome": "BUILD_GREEN", "output": str(build),
                  "outputTreeHash": "sha256:" + "a" * 64, "gitHead": "b" * 40,
                  "effects": EFFECTS, "images": {
                      key.replace(".", "-"): {"configDigest": "sha256:" + "c" * 64}
                      for key in VERSIONS}}
    build_receipt.write_text(json.dumps(build_data))
    qualified = tmp_path / "qualification.json"
    with pytest.raises(ValueError, match="QUALIFICATION_RECEIPT_REQUIRED"):
        profile.validate_qualification(build=build, build_receipt=build_receipt,
                                       qualification_receipt=qualified)
    claim = {"outcome": "QUALIFICATION_GREEN", "buildReceipt": str(build_receipt.resolve()),
             "buildReceiptHash": "sha256:" + hashlib.sha256(build_receipt.read_bytes()).hexdigest(),
             "outputTreeHash": build_data["outputTreeHash"], "gitHead": build_data["gitHead"],
             "effects": EFFECTS, "resolved": [{"id": key, "version": value} for key, value in VERSIONS.items()],
             "ephemeralSignaturePersisted": False,
             "tamperRejections": ["imageIndexBytes", "imageDigest", "dependencyLock",
                                  "sbom", "backend", "schemaCompatibility", "schemaRequirements"],
             "runtimeAdmissions": {key: {"imageId": "sha256:" + "c" * 64}
                                   for key in VERSIONS if key != "solution.ecommerce.operations-base"},
             "runtimeSessions": {key: {"cleanup": "released", "registration": "exact",
                                       "heartbeatChecks": 2048}
                                 for key in VERSIONS if key != "solution.ecommerce.operations-base"}}
    qualified.write_text(json.dumps(claim))
    profile.validate_qualification(build=build, build_receipt=build_receipt,
                                   qualification_receipt=qualified)
    claim["resolved"][2]["version"] = "1.12.0"
    qualified.write_text(json.dumps(claim))
    with pytest.raises(ValueError, match="QUALIFICATION_RECEIPT_MISMATCH"):
        profile.validate_qualification(build=build, build_receipt=build_receipt,
                                       qualification_receipt=qualified)
    claim["resolved"][2]["version"] = "1.13.0"
    claim["runtimeSessions"]["solution.ecommerce.growth"]["cleanup"] = "unknown"
    qualified.write_text(json.dumps(claim))
    with pytest.raises(ValueError, match="QUALIFICATION_RECEIPT_MISMATCH"):
        profile.validate_qualification(build=build, build_receipt=build_receipt,
                                       qualification_receipt=qualified)


def test_existing_signing_state_is_never_overwritten(profile, tmp_path, monkeypatch):
    signer = profile.load_signer()
    state = tmp_path / "state"
    state.mkdir()
    marker = state / "sentinel"
    marker.write_text("keep")
    monkeypatch.setattr(signer, "validate_build", lambda **_: (object(), {}))
    with pytest.raises(signer.SigningBlocked, match="STATE_ALREADY_EXISTS_RECONCILE_READ_ONLY"):
        signer.sign(build=tmp_path, receipt_path=tmp_path, state=state)
    assert marker.read_text() == "keep"
