import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_preview_bootstrap.py"


@pytest.fixture
def bootstrap():
    spec = importlib.util.spec_from_file_location("a0v_current_preview_bootstrap", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_new_migration_rejects_existing_state_without_writing(bootstrap, tmp_path, monkeypatch):
    assert bootstrap.HEAD == "a0v_107"
    state = tmp_path / "state"
    state.mkdir()
    marker = state / "keep"
    marker.write_text("retained", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "inspect_target", lambda: {
        "database": bootstrap.TARGET, "tableCount": 0, "versions": None,
    })
    with pytest.raises(bootstrap.BootstrapBlocked, match="TARGET_NOT_EMPTY_RECONCILE_READ_ONLY"):
        bootstrap.migrate(state=state)
    assert marker.read_text(encoding="utf-8") == "retained"


def test_resume_refuses_unverified_boundary(bootstrap, tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(bootstrap, "inspect_target", lambda: {
        "database": bootstrap.TARGET, "tableCount": 63, "versions": ["a0v_092"],
    })
    with pytest.raises(bootstrap.BootstrapBlocked, match="RESUME_BOUNDARY_NOT_EXACT"):
        bootstrap.migrate(state=state, resume_after_assetintegration=True)
    assert list(state.iterdir()) == []
