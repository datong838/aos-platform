import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]


def load():
    spec=importlib.util.spec_from_file_location('snapshot_clone',ROOT/'scripts/a0v_snapshot_schedule_clone.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_clone_profile_pins_complete_chain_and_main_cannot_upgrade(monkeypatch):
    m=load();p=m.profile()
    assert (p.SOURCE,p.TARGET)==('a0v_061','a0v_066')
    assert p.CHAIN==['a0v_066','a0v_065','a0v_064','a0v_063','a0v_062']
    assert len(p.storage.migration_hashes())==5 and len(m.NEW_TABLES)==7
    with pytest.raises(ValueError,match='clone only'):
        p.upgrade(p.storage.MAIN)
    assert p.storage.CLONE==m.CLONE


def test_executor_hashes_include_adapter_and_old_deployment_code():
    m=load();hashes=m.profile().executor_hashes()
    assert set(hashes)=={'a0v_snapshot_schedule_clone.py','a0v_installed_bootstrap_action_deploy.py',
                          'a0v_controlled_source_claim_deploy.py','env.py'}
    assert all(v.startswith('sha256:') and len(v)==71 for v in hashes.values())
