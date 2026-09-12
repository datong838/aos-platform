import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest


@pytest.fixture
def launcher(monkeypatch):
    root=Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('controlled_api_launcher_test',root/'scripts/a0v_controlled_api.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_api_flags_do_not_start_other_writers(launcher,monkeypatch):
    monkeypatch.setattr(launcher,'require_leases',lambda:None)
    configure=Mock()
    monkeypatch.setattr(launcher,'_configure_environment',configure)
    for key in launcher.API_FLAGS:
        monkeypatch.setenv(key,'test-original')
    launcher.configure_environment()
    configure.assert_called_once()
    import os
    for key,value in launcher.API_FLAGS.items():assert os.environ[key]==value
    assert os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0'
    assert os.environ['AOS_QYH_CRON_ENABLED']=='false'
    assert os.environ['AOS_JDBC_SSH_PREBUILD_ENABLED']=='false'
    assert os.environ['AOS_DB_MIGRATION_MODE']=='disabled'


def test_invalid_lease_blocks_before_environment(launcher,monkeypatch):
    configure=Mock()
    monkeypatch.setattr(launcher,'_configure_environment',configure)
    def deny():raise ValueError('lease unavailable')
    monkeypatch.setattr(launcher,'require_leases',deny)
    with pytest.raises(ValueError,match='lease unavailable'):launcher.configure_environment()
    configure.assert_not_called()
