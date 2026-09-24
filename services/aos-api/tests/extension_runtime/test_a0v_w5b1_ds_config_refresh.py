from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
import a0v_w5b1_ds_config_refresh as refresh


def test_fixed_profile_is_ds_only():
    p = refresh._profile()
    assert p.INSTALLATION == refresh.INSTALLATION
    assert p.GENERATION == refresh.GENERATION
    assert p.SOURCE_CONFIG == refresh.SOURCE_CONFIG
    assert p.STATE == refresh.STATE
    assert p.KEY == refresh.KEY


def test_stage_refuses_existing_state_before_database(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh, "STATE", tmp_path)
    monkeypatch.setattr(refresh, "preflight", lambda: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="EXISTING_STATE_RECONCILE_FIRST"):
        refresh.stage()


def test_configure_requires_frozen_stage(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh, "STATE", tmp_path)
    monkeypatch.setattr(refresh, "_command_count", lambda _: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="CONFIGURE_BOUNDARY_INVALID"):
        refresh.configure()


def test_enable_requires_frozen_configure(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh, "STATE", tmp_path)
    monkeypatch.setattr(refresh, "_command_count", lambda _: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="ENABLE_BOUNDARY_INVALID"):
        refresh.enable()
