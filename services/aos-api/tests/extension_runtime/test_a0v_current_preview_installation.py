import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_preview_installation.py"


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location("a0v_current_preview_installation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_existing_state_is_not_overwritten(installer, tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / "keep").write_text("retained", encoding="utf-8")
    monkeypatch.setattr(installer, "preflight", lambda **_: pytest.fail("preflight after state exists"))
    with pytest.raises(installer.InstallBlocked, match="STATE_MUST_BE_NEW_OUTSIDE_REPOSITORY"):
        installer.apply(signed_receipt=tmp_path, state=state)
    assert (state / "keep").read_text(encoding="utf-8") == "retained"


def test_missing_signing_receipt_rejected_before_database_access(installer, tmp_path, monkeypatch):
    receipt = tmp_path / "signing-receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(installer, "_load", lambda *_: pytest.fail("module loaded"))
    with pytest.raises(installer.InstallBlocked, match="SIGNING_RECEIPT_DRIFT"):
        installer.preflight(signed_receipt=receipt)
