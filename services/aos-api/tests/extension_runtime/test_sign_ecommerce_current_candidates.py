import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/sign_ecommerce_current_candidates.py"


@pytest.fixture
def signer():
    spec = importlib.util.spec_from_file_location("sign_ecommerce_current_candidates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_repository_target_is_rejected_before_any_write(signer, tmp_path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    with pytest.raises(signer.SigningBlocked, match="PATH_MUST_BE_OUTSIDE_REPOSITORY"):
        signer.validate_build(build=signer.ROOT, receipt_path=receipt, state=tmp_path / "state")
    assert not (tmp_path / "state").exists()


def test_mismatched_build_receipt_is_rejected_before_any_write(signer, tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"outcome": "BUILD_GREEN", "output": str(build)}), encoding="utf-8")
    with pytest.raises(signer.SigningBlocked, match="BUILD_RECEIPT_MISMATCH"):
        signer.validate_build(build=build, receipt_path=receipt, state=tmp_path / "state")
    assert not (tmp_path / "state").exists()


def test_existing_state_is_not_overwritten(signer, tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    sentinel = state / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(signer, "validate_build", lambda **_: (object(), {}))
    with pytest.raises(signer.SigningBlocked, match="STATE_ALREADY_EXISTS_RECONCILE_READ_ONLY"):
        signer.sign(build=tmp_path, receipt_path=tmp_path, state=state)
    assert sentinel.read_text(encoding="utf-8") == "keep"
