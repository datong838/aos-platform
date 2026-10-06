"""Pure receipt identity gate tests; no claim of real maintenance execution."""
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
import pytest


def module():
    spec=importlib.util.spec_from_file_location('maintenance151',Path(__file__).resolve().parents[1]/'a0v_current_151_maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('fault',['owner','thread','status','base','lease_missing','lease_duplicate','lease_drift','expired','naive','delivered','scope','authority'])
def test_maintenance_rejects_unbound_or_stale_receipt(fault):
    m=module();now=datetime(2026,10,6,11,tzinfo=timezone.utc)
    task=dict(task_id=m.TASK,owner=m.OWNER,status='ACTIVE',base_revision='AOS-001369',scope=list(m.SCOPES),lease_expires_at='2026-10-07T00:00:00+00:00')
    leases=[dict(task)];revision='AOS-001369';delivered=False;thread=m.THREAD
    if fault=='owner':task['owner']='other'
    elif fault=='thread':thread='old-thread'
    elif fault=='status':task['status']='COMPLETE'
    elif fault=='base':task['base_revision']='AOS-001368'
    elif fault=='lease_missing':leases=[]
    elif fault=='lease_duplicate':leases.append(dict(task))
    elif fault=='lease_drift':leases[0]['excluded_scope']=['changed']
    elif fault=='expired':task['lease_expires_at']='2026-10-06T10:00:00+00:00';leases=[dict(task)]
    elif fault=='naive':task['lease_expires_at']='2026-10-07T00:00:00';leases=[dict(task)]
    elif fault=='delivered':delivered=True
    elif fault=='scope':task['scope']=[];leases=[dict(task)]
    elif fault=='authority':revision='AOS-001370'
    with pytest.raises(m.Maintenance151Blocked):m.require_task(task,leases,revision=revision,thread=thread,delivered=delivered,now=now)


def test_bound_active_receipt_is_only_preflight_permission():
    m=module();task=dict(task_id=m.TASK,owner=m.OWNER,status='ACTIVE',base_revision='AOS-001369',scope=list(m.SCOPES),lease_expires_at='2026-10-07T00:00:00+00:00')
    assert m.require_task(task,[dict(task)],revision='AOS-001369',thread=m.THREAD,delivered=False,now=datetime(2026,10,6,tzinfo=timezone.utc)) is None


@pytest.mark.parametrize('fault',['source_id','source_image','source_volume','target_image','target_volume'])
def test_restore_identity_rejects_replacement_resources(fault):
    m=module()
    expected=dict(source_id='source',source_image='image',source_volume='source-volume',target_image='image',target_volume='target-volume')
    observed=dict(expected);observed[fault]='replacement'
    with pytest.raises(m.Maintenance151Blocked):m.require_resource_identity(expected,observed)


def test_timeout_attempt_cannot_be_reissued(tmp_path,monkeypatch):
    m=module();calls=[];j=m.Maintenance151Journal(tmp_path,head='a'*40)
    monkeypatch.setattr(j,'_require_live_binding',lambda: None)
    def unknown():
        calls.append(1);raise TimeoutError('unknown effect')
    with pytest.raises(TimeoutError):j.perform('stop_clients',unknown)
    with pytest.raises(m.Maintenance151Blocked):j.perform('stop_clients',lambda: calls.append(2))
    assert calls==[1]


def test_changed_head_or_unverified_result_cannot_advance(tmp_path,monkeypatch):
    m=module();j=m.Maintenance151Journal(tmp_path,head='a'*40)
    monkeypatch.setattr(j,'_require_live_binding',lambda: None)
    j.perform('stop_clients',lambda: dict(status='verified',ports=[]))
    with pytest.raises(m.Maintenance151Blocked):m.Maintenance151Journal(tmp_path,head='b'*40).perform('fence_tcp',lambda: dict(status='verified'))
    with pytest.raises(m.Maintenance151Blocked):j.perform('fence_tcp',lambda: dict(status='failed'))
    assert not (tmp_path/'fence_tcp-done.json').exists()


@pytest.mark.parametrize('fault',['head','branch','task'])
def test_live_drift_prevents_operation_and_attempt(tmp_path,monkeypatch,fault):
    import subprocess
    m=module();calls=[];j=m.Maintenance151Journal(tmp_path,head='a'*40)
    def task(**kwargs):
        if fault=='task':raise m.Maintenance151Blocked('MAINTENANCE_151_FUTURE_LEASE_REQUIRED')
        return dict(task_id=m.TASK)
    monkeypatch.setattr(m,'read_task',task)
    def git(args,**kwargs):
        if args[-1]=='HEAD':return ('b' if fault=='head' else 'a')*40+'\n'
        return ('other' if fault=='branch' else 'm1')+'\n'
    monkeypatch.setattr(subprocess,'check_output',git)
    with pytest.raises(m.Maintenance151Blocked):
        j.perform('stop_clients',lambda: calls.append(1))
    assert calls==[]
    assert not (tmp_path/'stop_clients-attempt.json').exists()


def test_drift_after_intent_preserves_unknown_attempt_without_effect(tmp_path,monkeypatch):
    m=module();calls=[];checks=[];j=m.Maintenance151Journal(tmp_path,head='a'*40)
    def check():
        checks.append(1)
        if len(checks)==2:raise m.Maintenance151Blocked('EXECUTION_HEAD_DRIFT')
    monkeypatch.setattr(j,'_require_live_binding',check)
    with pytest.raises(m.Maintenance151Blocked):j.perform('stop_clients',lambda: calls.append(1))
    assert calls==[]
    assert (tmp_path/'stop_clients-attempt.json').exists()
    assert not (tmp_path/'stop_clients-done.json').exists()
