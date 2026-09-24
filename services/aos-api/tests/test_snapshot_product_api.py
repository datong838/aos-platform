import importlib.util
import json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))


def load():
    spec=importlib.util.spec_from_file_location('snapshot_api',ROOT/'scripts/a0v_snapshot_product_api.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_profile_keeps_single_external_host_and_original_defaults():
    m=load();p=m.load_launcher()
    assert m.TASK=='A0V-BL-SNAPSHOT-WORKER-20260920'
    assert str(m.STATE).endswith('.aos-recovery-20260920/state/q-advisor-baseline/replacement-bl/snapshot-worker')
    assert p.API_FLAGS['AOS_SNAPSHOT_GROUP_WORKER_ENABLED']=='true'
    assert p.API_FLAGS['AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY']=='independent'
    for key in ('AOS_EXTENSION_RUNTIME_HOST_ENABLED','AOS_QYH_CRON_ENABLED','AOS_AIP_LOGIC_AUTOMATION_ENABLED'):
        assert p.API_FLAGS[key] in ('0','false')
    from a0v_event_complete_product_api import load_launcher
    original=load_launcher()
    assert original.API_FLAGS['AOS_SNAPSHOT_GROUP_WORKER_ENABLED']=='false'
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


def test_w5c4p_worker_lease_requires_exact_port_scope(tmp_path, monkeypatch):
    m = load()
    repo = tmp_path / 'repo'
    repo.mkdir()
    leases = tmp_path / 'docs/palantier/AOS项目开发上下文/memory/leases.json'
    leases.parent.mkdir(parents=True)
    monkeypatch.setattr(m, 'ROOT', repo)
    monkeypatch.setattr(m, 'TASK', 'A0V-W5C4P-SNAPSHOT-WORKER-20260924')
    monkeypatch.setattr(sys, 'argv', ['snapshot', 'check'])
    called = []
    monkeypatch.setattr(m, 'load_launcher', lambda: type('Launcher', (), {
        'main': lambda self: called.append(True)})())
    entry = dict(task_id=m.TASK, owner='m1', status='ACTIVE',
                 scope=['local-process/aos-api-18181'],
                 lease_expires_at='2099-01-01T00:00:00+00:00')
    leases.write_text(json.dumps({'leases': [entry]}))
    m.main()
    assert called == [True]
    leases.write_text(json.dumps({'leases': [{**entry, 'scope': ['other']}]}))
    with pytest.raises(ValueError, match='current snapshot API lease required'):
        m.main()
    assert called == [True]
