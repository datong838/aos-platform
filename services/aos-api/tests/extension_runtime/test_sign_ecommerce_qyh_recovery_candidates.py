"""Exact recovery signer input validation without generating a key or signature."""
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
BUILD = ROOT.parent / "aos-recovery/.aos-qyh-core143-build-20261011-r1"
RECEIPT = ROOT / ".evidence/qyh-core143-actual-build-20261011/build-receipt.json"
QUALIFICATION = ROOT / ".evidence/qyh-core143-actual-build-20261011/qualification-receipt.json"


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("sign_ecommerce_qyh_recovery_candidates")


def test_real_qualified_build_validate_only_never_signs(profile, tmp_path, monkeypatch, capsys):
    assert BUILD.is_dir() and RECEIPT.is_file() and QUALIFICATION.is_file()
    state = tmp_path / "state"
    signer = profile.load_signer()
    def forbidden(**kwargs):
        pytest.fail("read-only validation invoked signing")
    monkeypatch.setattr(signer, "sign", forbidden)
    monkeypatch.setattr(signer, "_key", forbidden)
    monkeypatch.setattr(profile, "load_signer", lambda: signer)
    assert profile.main(["--build-dir", str(BUILD), "--build-receipt", str(RECEIPT),
                         "--qualification-receipt", str(QUALIFICATION),
                         "--state-dir", str(state), "--validate-only"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "VALIDATED_UNSIGNED_BUILD_NO_SIGN"
    assert result["versions"]["domain.ecommerce.core"] == "1.4.3"
    assert not state.exists() and not list(BUILD.rglob("bundle.signature.json"))


@pytest.mark.parametrize("mutation", ["version", "heartbeat", "buildHash"])
def test_wrong_qualification_rejected_without_state(profile, tmp_path, mutation):
    document = json.loads(QUALIFICATION.read_text())
    if mutation == "version":
        document["resolved"][0]["version"] = "1.4.0"
    elif mutation == "heartbeat":
        document["runtimeSessions"]["domain.ecommerce.core"]["heartbeatChecks"] = 2047
    else:
        document["buildReceiptHash"] = "sha256:" + "0" * 64
    path = tmp_path / "wrong-qualified.json"
    path.write_text(json.dumps(document))
    state = tmp_path / "state"
    with pytest.raises(ValueError, match="QUALIFICATION_RECEIPT_MISMATCH"):
        profile.validate_inputs(build=BUILD, build_receipt=RECEIPT,
                                qualification_receipt=path, state=state)
    assert not state.exists()


def test_old_signer_profile_unchanged(profile):
    signer = profile.load_signer()
    assert signer.PROFILE.name == "build_ecommerce_qyh_recovery_candidates.py"
    assert signer.KEY_ID == "a0v-local-qyh-core143-growth113-v1"
    assert {item["id"]: item["version"] for item in signer._builder().preflight()["bundles"]} == profile.VERSIONS
    old = importlib.import_module("sign_ecommerce_growth_1_13_candidates")
    assert old.VERSIONS["domain.ecommerce.core"] == "1.4.0"
    assert old.load_signer().PROFILE.name == "build_ecommerce_growth_1_13_candidates.py"


@pytest.mark.parametrize("relative", ["bundle.yaml", "../state/receipt.json"])
def test_receipt_output_cannot_corrupt_inputs_or_state(profile, tmp_path, relative):
    build = tmp_path / "build"
    state = tmp_path / "state"
    build.mkdir()
    output = build / relative
    with pytest.raises(ValueError, match="SIGNING_OUTPUT_INVALID"):
        profile.validate_output(output=output, build=build, state=state)
    assert not state.exists()


def test_dangling_receipt_symlink_is_rejected(profile, tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    target = tmp_path / "unintended-receipt.json"
    link = tmp_path / "receipt-link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="SIGNING_OUTPUT_INVALID"):
        profile.validate_output(output=link, build=build, state=tmp_path / "state")
    assert not target.exists()
