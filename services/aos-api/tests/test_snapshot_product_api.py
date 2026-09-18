import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]


def load():
    spec=importlib.util.spec_from_file_location('snapshot_api',ROOT/'scripts/a0v_snapshot_product_api.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_profile_keeps_single_external_host_and_original_defaults():
    m=load();p=m.load_launcher()
    assert p.API_FLAGS['AOS_SNAPSHOT_GROUP_WORKER_ENABLED']=='true'
    assert p.API_FLAGS['AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY']=='independent'
    for key in ('AOS_EXTENSION_RUNTIME_HOST_ENABLED','AOS_QYH_CRON_ENABLED','AOS_AIP_LOGIC_AUTOMATION_ENABLED'):
        assert p.API_FLAGS[key] in ('0','false')
    from a0v_event_complete_product_api import load_launcher
    original=load_launcher()
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED' not in original.API_FLAGS
    assert set(m.CODE_HASHES) >= {
        'services/aos-api/aos_api/pipeline_snapshot_group_completion.py',
        'services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py',
    }
    assert all(value.startswith('sha256:') and len(value) == 71 for value in m.CODE_HASHES.values())


def test_api_lock_conflict_prevents_second_owner(tmp_path):
    m=load();lock=tmp_path/'api.lock'
    with m.api_lock(lock):
        with pytest.raises(BlockingIOError):
            with m.api_lock(lock):pytest.fail('second owner')
    with m.api_lock(lock):pass
