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


@pytest.mark.parametrize('select',['SELECT ','SELECT\n'])
def test_readonly_catalog_adapter_preserves_native_types_and_literal_parameters(select):
    m=module();queries=[]
    def query(s):
        queries.append(s)
        return [dict(oid='12',atttypid='25',polroles=['12'],tgargs='\\x',prosrc='12')]
    c=m.ReadOnlyCatalogConnection(query)
    row=c.execute(select+'%s AS value',("a'quoted",)).fetchone()
    assert row==dict(oid=12,atttypid=25,polroles=[12],tgargs=b'',prosrc='12')
    assert "'a''quoted'" in queries[0]


@pytest.mark.parametrize('statement',['UPDATE x SET y=1','SELECT 1; SELECT 2'])
def test_readonly_catalog_adapter_rejects_effects_or_multiple_statements(statement):
    m=module();calls=[];c=m.ReadOnlyCatalogConnection(lambda s: calls.append(s))
    with pytest.raises(m.Maintenance151Blocked):c.execute(statement)
    assert calls==[]


@pytest.mark.parametrize('fault',['source_name','network','ports','image','volume'])
def test_isolated151_refuses_current_or_drifted_resource(fault):
    m=module();name='current151-source-abcd'
    item=dict(Name='/'+name,Image='image',State=dict(Running=True),HostConfig=dict(NetworkMode='none',Privileged=False),NetworkSettings=dict(Ports={}),Mounts=[dict(Type='volume',Name=name+'-data',Destination='/var/lib/postgresql/data',RW=True)])
    if fault=='source_name':name='aos-a0v-recovery-pg';item['Name']='/'+name
    elif fault=='network':item['HostConfig']['NetworkMode']='bridge'
    elif fault=='ports':item['NetworkSettings']['Ports']={'5432/tcp':[dict(HostPort='18435')]}
    elif fault=='image':item['Image']='other'
    elif fault=='volume':item['Mounts'][0]['Name']='aos-a0v-recovery-pg-data'
    with pytest.raises(m.Maintenance151Blocked):m.require_isolated151(item,name=name,image='image')


@pytest.mark.parametrize('fault',['payload','old_row','unknown_id'])
def test_metadata_timestamp_equivalence_rejects_other_changes(fault):
    import copy
    m=module();ids=m.METADATA151_ADDITIONS
    before=dict(metadata={t:{'old':'same'} for t in ids})
    actual=dict(metadata={t:{'old':'same',**{i:'newhash' for i in names}} for t,names in ids.items()},tables={t:dict(count=3,sha256='new') for t in ids})
    expected=copy.deepcopy(actual)
    rows={t:[dict(id=i,created_at='2026-10-05T10:00:00+00:00',value='same') for i in names] for t,names in ids.items()}
    live=copy.deepcopy(rows)
    for entries in live.values():
        for row in entries:row['created_at']='2026-10-06T10:00:00+00:00'
    if fault=='payload':next(iter(live.values()))[0]['value']='changed'
    elif fault=='old_row':next(iter(actual['metadata'].values()))['old']='changed'
    else:next(iter(live.values()))[0]['id']='other'
    with pytest.raises(m.Maintenance151Blocked):m.normalize_metadata151(before,expected,actual,rows,live)


@pytest.mark.parametrize('action',['run','rm','stop','volume'])
def test_current151_denies_unreviewed_docker_actions(action):
    m=module()
    with pytest.raises(m.Maintenance151Blocked):m.require_current151_action([action,'aos-a0v-recovery-pg'])


def test_current151_wrong_thread_cannot_enter_sequence(monkeypatch):
    m=module();calls=[]
    def task(**kwargs):
        assert kwargs['thread']=='old-thread'
        raise m.Maintenance151Blocked('MAINTENANCE_151_BASELINE_DRIFT')
    monkeypatch.setattr(m,'read_task',task)
    monkeypatch.setattr(m,'preflight',lambda **kwargs: calls.append(1))
    with pytest.raises(m.Maintenance151Blocked):m.run_current151(thread='old-thread')
    assert calls==[]


def test_service_identity_drift_prevents_signal(monkeypatch):
    import os
    from types import SimpleNamespace
    m=module();signals=[]
    monkeypatch.setattr(os,'kill',lambda *args: signals.append(args))
    def refuse(*args,**kwargs):raise m.Maintenance151Blocked('PROCESS_IDENTITY_DRIFT')
    maintenance=SimpleNamespace(read_service_candidate=lambda **kwargs:dict(pid=2),require_process=refuse)
    journal=SimpleNamespace(_require_live_binding=lambda:None)
    service=dict(fingerprint=dict(pid=123),argv=['original'],cwd='original',port=8080,helper_argv=None)
    with pytest.raises(m.Maintenance151Blocked):m.stop_services151([service],journal=journal,maintenance=maintenance)
    assert signals==[]


def test_schema_mismatch_prevents_start(monkeypatch):
    import subprocess,json
    from types import SimpleNamespace
    m=module();started=[]
    monkeypatch.setattr(subprocess,'Popen',lambda *args,**kwargs:started.append(1))
    def run(args,**kwargs):
        if args[0]=='lsof':return SimpleNamespace(stdout=b'')
        return SimpleNamespace(returncode=0,stdout=json.dumps(dict(outcome='CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN',version='a0v_142')).encode())
    monkeypatch.setattr(subprocess,'run',run)
    journal=SimpleNamespace(_require_live_binding=lambda:None)
    service=dict(port=8080,argv=['python','api','--serve'],cwd='original')
    with pytest.raises(m.Maintenance151Blocked):m.restart_services151([service],journal=journal,maintenance=None)
    assert started==[]


def tenant_rows151():
    return {
        'meta_org':[dict(id='org-org',name='preserved',updated_at='2026-10-01T00:00:00+00:00')],
        'meta_workspace':[dict(org_id='org-org',project_id='dev-project',name='preserved',updated_at='2026-10-01T00:00:00+00:00')],
        'meta_membership':[dict(org_id='org-org',project_id='dev-project',subject='existing',role='viewer',updated_at='2026-10-01T00:00:00+00:00')],
    }


@pytest.mark.parametrize('fault',['field','rows','table','tenant','workspace','same','naive','backwards'])
def test_timestamp_repair_rejects_other_changes_or_replay(fault):
    import copy
    m=module();old=tenant_rows151();live=copy.deepcopy(old)
    for rows in live.values():rows[0]['updated_at']='2026-10-06T00:00:00+00:00'
    if fault=='field':live['meta_membership'][0]['role']='owner'
    elif fault=='rows':live['meta_org'].append(dict(live['meta_org'][0]))
    elif fault=='table':live['unexpected']=[]
    elif fault=='tenant':old['meta_org'][0]['id']=live['meta_org'][0]['id']='dev-org'
    elif fault=='workspace':old['meta_workspace'][0]['project_id']=live['meta_workspace'][0]['project_id']='other'
    elif fault=='same':live['meta_org'][0]['updated_at']=old['meta_org'][0]['updated_at']
    elif fault=='naive':live['meta_org'][0]['updated_at']='2026-10-06T00:00:00'
    elif fault=='backwards':live['meta_org'][0]['updated_at']='2026-09-01T00:00:00+00:00'
    with pytest.raises(m.Maintenance151Blocked):m.build_tenant_timestamp_repair151(old,live)


def test_timestamp_repair_sql_has_exact_cas_and_atomic_row_count_guard():
    import copy
    m=module();old=tenant_rows151();live=copy.deepcopy(old)
    for rows in live.values():rows[0]['updated_at']='2026-10-06T00:00:00+00:00'
    sql=m.build_tenant_timestamp_repair151(old,live).as_string()
    assert sql.startswith('BEGIN;') and sql.endswith('COMMIT;')
    assert sql.count('SET updated_at=')==3
    assert sql.count('row_to_json(t)::jsonb =')==3
    assert sql.count('ROW_COUNT')==3
    assert 'RAISE EXCEPTION' in sql
    assert 'alembic_version' not in sql and 'ALTER' not in sql and 'DELETE' not in sql


def history151(m):
    binding=dict(head='ebac8fd094a8202b0e08f436cd9c09e8a0207d75',thread=m.THREAD,task=m.TASK,authority=m.BASE)
    records={'intent.json':dict(binding=binding,source='aos-a0v-recovery-pg',source_touched=True,target='current151-restore-da8531053c83')}
    for step in m.STEPS:
        records[step+'-attempt.json']=dict(binding=binding,step=step)
        if step!='acceptance':records[step+'-done.json']=dict(binding=binding,step=step,result=dict(status='verified'))
    for n in range(143,152):
        records[f'migration-{n}-attempt.json']=dict(binding=binding,sha256='a'*64)
        records[f'migration-{n}-terminal.json']=dict(exit_code=0)
    return records


@pytest.mark.parametrize('fault',['missing','binding','failed','unknown_migration','accepted','wrong_source'])
def test_repair_requires_exact_terminal_failed_window_history(fault):
    m=module();records=history151(m)
    if fault=='missing':records.pop('verify-done.json')
    elif fault=='binding':records['restart_clients-done.json']['binding']=dict(head='b'*40)
    elif fault=='failed':records['migration-151-terminal.json']['exit_code']=1
    elif fault=='unknown_migration':records.pop('migration-150-terminal.json')
    elif fault=='accepted':records['acceptance-done.json']=dict(status='verified')
    elif fault=='wrong_source':records['intent.json']['source']='replacement'
    with pytest.raises(m.Maintenance151Blocked):m.require_failed_window151(records)


def test_repair_journal_has_no_migration_and_refuses_replay(tmp_path,monkeypatch):
    m=module();assert m.require_failed_window151(history151(m))['head'].startswith('ebac')
    j=m.Repair151Journal(tmp_path,head='a'*40);monkeypatch.setattr(j,'_require_live_binding',lambda:None)
    j.perform('reconcile',lambda:dict(status='verified'))
    with pytest.raises(m.Maintenance151Blocked):j.perform('migrate_steps',lambda:dict(status='verified'))
    with pytest.raises(m.Maintenance151Blocked):j.perform('reconcile',lambda:dict(status='verified'))


def test_current_repair_wrong_thread_never_touches_resources(monkeypatch):
    m=module();calls=[]
    def denied(*,thread):
        assert thread=='old-thread'
        raise m.Maintenance151Blocked('wrong thread')
    monkeypatch.setattr(m,'read_task',denied)
    import subprocess
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:calls.append(a))
    with pytest.raises(m.Maintenance151Blocked):m.run_current151_repair(thread='old-thread')
    assert calls==[]


def repair_parent151(m):
    b=dict(head='34063052b0dc02ed497ab0501294efe86fc355c1',thread=m.THREAD,task=m.TASK,authority=m.BASE)
    records={'intent.json':dict(binding=b,source='aos-a0v-recovery-pg')}
    for step in ('reconcile','stop_clients','fence_tcp','snapshot_dump','independent_restore'):
        records[step+'-attempt.json']=dict(binding=b,step=step)
        if step!='independent_restore':records[step+'-done.json']=dict(binding=b,step=step,result=dict(status='verified'))
    return records,dict(binding=b,state='/Users/ddt/work/projects/ai_agent/aos-recovery/current151-repair-e1d51a4f1798')


@pytest.mark.parametrize('fault',['missing','binding','accepted_restore','later_attempt','claim','failed_prior'])
def test_recovery_refuses_unverified_or_already_started_parent(fault):
    m=module();records,claim=repair_parent151(m)
    if fault=='missing':records.pop('snapshot_dump-done.json')
    elif fault=='binding':records['independent_restore-attempt.json']['binding']=dict(head='x')
    elif fault=='accepted_restore':records['independent_restore-done.json']=dict(status='verified')
    elif fault=='later_attempt':records['repair_timestamps-attempt.json']=dict(status='unknown')
    elif fault=='claim':claim['state']='different'
    elif fault=='failed_prior':records['stop_clients-done.json']['result']['status']='failed'
    with pytest.raises(m.Maintenance151Blocked):m.require_recovery_parent151(records,claim)


def test_recovery_consumes_real_parent_without_fabricating_prior_steps(tmp_path,monkeypatch):
    m=module();records,claim=repair_parent151(m);m.require_recovery_parent151(records,claim)
    j=m.Recovery151Journal(tmp_path,head='a'*40);monkeypatch.setattr(j,'_require_live_binding',lambda:None)
    assert 'snapshot_dump' not in j.steps and 'stop_clients' not in j.steps
    j.perform('reconcile',lambda:dict(status='verified'))
    j.perform('independent_restore',lambda:dict(status='verified'))
    with pytest.raises(m.Maintenance151Blocked):j.perform('independent_restore',lambda:dict(status='verified'))
