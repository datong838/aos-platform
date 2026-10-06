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
