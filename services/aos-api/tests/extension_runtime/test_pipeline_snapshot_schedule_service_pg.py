"""Committed service transactions with original runtime role and permission gate."""
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
import pytest

from test_analysis_snapshot_native_ingress_pg import private_database,stored
from test_analysis_snapshot_native_claims_pg import native_claims_case,host_case,control_governed,governed,service_case,pair,body
from test_pipeline_snapshot_schedule_claim_pg import schedule_group
from test_pipeline_snapshot_schedule_definition_pg import definition_case
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.pipeline_snapshot_schedule_service import PipelineSnapshotScheduleService
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def service(definition_case,private_database,monkeypatch):
    conn,owner,args=definition_case
    controls=owner._groups._groups._controls
    plans={}
    owner._groups._groups.run_current(conn,scope=args['scope'],actor=args['actor'],
        refs=tuple(b.control_ref for b in args['bindings']),
        execute=lambda g:plans.update({draft.pipeline_id:plan for _,draft,plan in g.members}))
    def named_assets(db,draft,actor,consume,*,snapshot=False):
        assert db.info.dbname==conn.info.dbname and actor==args['actor']
        plan=plans[draft.pipeline_id]
        return consume(plan if snapshot else plan.read_spec)
    controls._selections._guarded=named_assets
    conn.commit()
    @contextmanager
    def runtime_connect():
        with psycopg.connect(private_database,row_factory=dict_row,autocommit=True) as db:
            db.execute('SET SESSION AUTHORIZATION aos_runtime')
            db.autocommit=False
            yield db
    import aos_api.pipeline_snapshot_schedule_service as module
    monkeypatch.setattr(module,'runtime_worker_connection',runtime_connect)
    service=PipelineSnapshotScheduleService(scope=args['scope'],controls=controls,installation_store=PostgresInstallationStore())
    command={k:v for k,v in args.items() if k not in {'scope','bindings'}}
    command['members']=[dict(scheduleId=b.schedule_id,bindingRef=b.ref.model_dump(mode='json',by_alias=True,exclude_none=True)) for b in args['bindings']]
    return service,command,private_database,controls


def test_committed_configuration_replays_and_reads_across_connections(service):
    owner,args,database,_=service
    first=owner.configure(**args)
    assert owner.configure(**args)==first
    common={k:args[k] for k in ('definition_id','actor')}
    assert owner.read(**common)==first
    enabled=owner.transition(**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    assert owner.read(**common)==enabled
    disabled=owner.transition(**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='disable')
    assert owner.read(**common)==disabled
    with psycopg.connect(database,row_factory=dict_row) as db:
        assert db.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_definition_revision').fetchone()['n']==3
        assert db.execute('SELECT count(*) AS n FROM meta_schedule WHERE enabled').fetchone()['n']==0
        assert db.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==0
        assert db.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_stale_binding_and_negative_tenant_leave_no_configuration(service):
    owner,args,database,controls=service
    from copy import deepcopy
    bad=deepcopy(args);bad['members'][-1]['bindingRef']['revision']+=1
    with pytest.raises(ValueError,match='not current'):owner.configure(**bad)
    negative=PipelineSnapshotScheduleService(scope=TenantScope('dev-org','dev-project'),controls=controls,installation_store=PostgresInstallationStore())
    with pytest.raises(ValueError,match='not current'):negative.configure(**args)
    with pytest.raises(LookupError):negative.read(definition_id=args['definition_id'],actor=args['actor'])
    with psycopg.connect(database,row_factory=dict_row) as db:
        assert db.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_definition_revision').fetchone()['n']==0


def test_read_and_replay_recheck_current_persisted_membership(service):
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    owner,args,database,_=service
    owner.configure(**args)
    with psycopg.connect(database) as db:
        db.execute('DELETE FROM meta_membership WHERE subject=%s',(args['actor'],))
    with pytest.raises(RuntimeConflict,match='membership'):owner.read(definition_id=args['definition_id'],actor=args['actor'])
    with pytest.raises(RuntimeConflict,match='membership'):owner.configure(**args)


def test_stop_only_service_preserves_current_permission_and_cannot_enable(service):
    owner,args,_,_=service
    first=owner.configure(**args)
    common={k:args[k] for k in ('definition_id','actor')}
    enabled=owner.transition(**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    stop=PipelineSnapshotScheduleService(scope=owner.scope,controls=None,installation_store=PostgresInstallationStore())
    disabled=stop.transition(**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='stop-only')
    assert stop.read(**common)==disabled
    with pytest.raises(PermissionError,match='stop-only'):
        stop.transition(**common,intent='enable',expected_ref=disabled['ref'],idempotency_key='forbidden')


def test_original_key_readback_survives_later_retirement(service):
    owner,args,database,_=service
    first=owner.configure(**args)
    common={k:args[k] for k in ('definition_id','actor')}
    retired=owner.transition(**common,intent='retire',expected_ref=first['ref'],idempotency_key='retire')
    receipt=owner.read_receipt(**common,idempotency_key=args['idempotency_key'])
    assert receipt['ref']==first['ref'] and receipt['body']==first['body']
    assert receipt['idempotencyKey']==args['idempotency_key']
    assert receipt['request']['intent']=='configure'
    assert owner.read(**common)==retired
    with pytest.raises(LookupError):owner.read_receipt(**common,idempotency_key='uncommitted')
    with psycopg.connect(database,row_factory=dict_row) as db:
        assert db.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_definition_revision').fetchone()['n']==2


def test_list_and_receipt_are_scoped_and_permission_checked(service):
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    owner,args,database,_=service
    first=owner.configure(**args)
    result=owner.list(actor=args['actor'])
    assert result=={'items':[first],'nextCursor':None}
    assert owner.list(actor=args['actor'],after=args['definition_id'])=={'items':[],'nextCursor':None}
    negative=PipelineSnapshotScheduleService(scope=TenantScope('dev-org','dev-project'),controls=None,installation_store=PostgresInstallationStore())
    assert negative.list(actor=args['actor'])=={'items':[],'nextCursor':None}
    with pytest.raises(LookupError):negative.read_receipt(definition_id=args['definition_id'],actor=args['actor'],idempotency_key=args['idempotency_key'])
    with psycopg.connect(database) as db:db.execute('DELETE FROM meta_membership WHERE subject=%s',(args['actor'],))
    with pytest.raises(RuntimeConflict,match='membership'):owner.list(actor=args['actor'])
    with pytest.raises(RuntimeConflict,match='membership'):owner.read_receipt(definition_id=args['definition_id'],actor=args['actor'],idempotency_key=args['idempotency_key'])


def test_pagination_covers_definitions_without_duplicates(service):
    from uuid import uuid4
    owner,args,_,_=service
    identifiers=sorted(str(uuid4()) for _ in range(3))
    for identifier in reversed(identifiers):
        first=owner.configure(**(args|{'definition_id':identifier}))
        owner.transition(definition_id=identifier,actor=args['actor'],intent='retire',
            expected_ref=first['ref'],idempotency_key='retire')
    first_page=owner.list(actor=args['actor'],limit=2)
    assert [r['body']['definitionId'] for r in first_page['items']]==identifiers[:2]
    assert first_page['nextCursor']==identifiers[1]
    second_page=owner.list(actor=args['actor'],after=first_page['nextCursor'],limit=2)
    assert [r['body']['definitionId'] for r in second_page['items']]==identifiers[2:]
    assert second_page['nextCursor'] is None


def test_options_resolve_current_bindings_and_installed_policy_without_reads(service):
    owner,args,database,_=service
    with psycopg.connect(database,row_factory=dict_row) as db:
        target=db.execute('SELECT installation_id,generation FROM pipeline_schedule_control_binding LIMIT 1').fetchone()
    options=owner.options(actor=args['actor'],installation_id=str(target['installation_id']),generation=str(target['generation']))
    assert options['status']=='ready'
    assert len(options['members'])==12 and options['missing']==[] and options['ambiguous']==[]
    assert options['policies']==[args['policy_ref'].model_dump(mode='json',by_alias=True,exclude_none=True)]
    assert {m['scheduleId'] for m in options['members']}=={m['scheduleId'] for m in args['members']}
    with psycopg.connect(database,row_factory=dict_row) as db:
        assert db.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0
        assert db.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_definition_head').fetchone()['n']==0


def option_target(database):
    with psycopg.connect(database,row_factory=dict_row) as db:
        row=db.execute('SELECT installation_id,generation FROM pipeline_schedule_control_binding LIMIT 1').fetchone()
    return dict(installation_id=str(row['installation_id']),generation=str(row['generation']))


@pytest.mark.parametrize('schedule_group',['eleven'],indirect=True)
def test_options_report_missing_source_without_synthesizing_member(service):
    owner,args,database,_=service
    value=owner.options(actor=args['actor'],**option_target(database))
    assert value['status']=='incomplete' and len(value['missing'])==1
    assert value['members']==[] and value['policies']==[]


def test_duplicate_current_pipeline_requires_resolution(service):
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    owner,args,database,controls=service
    with psycopg.connect(database,row_factory=dict_row) as db:
        db.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",owner.scope.key)
        db.execute('SET LOCAL ROLE aos_runtime')
        binding=PipelineScheduleControlOwner.read_latest(db,scope=owner.scope,schedule_id=args['members'][0]['scheduleId'])
        db.execute("""INSERT INTO meta_schedule(id,org_id,project_id,name,cron,pipeline_id,enabled,ingest)
            SELECT 'duplicate-source',org_id,project_id,'duplicate','0 8 * * *',pipeline_id,false,ingest
            FROM meta_schedule WHERE id=%s""",(binding.schedule_id,))
        PipelineScheduleControlOwner(controls=controls).bind(db,scope=owner.scope,schedule_id='duplicate-source',
            control_ref=binding.control_ref,actor=args['actor'],idempotency_key='duplicate')
    value=owner.options(actor=args['actor'],**option_target(database))
    assert value['status']=='incomplete' and value['ambiguous']==[binding.pipeline_id]
    assert value['members']==[] and value['policies']==[]


def test_no_relationship_policy_and_revoked_permission_do_not_offer_ready(service):
    from types import SimpleNamespace as NS
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    owner,args,database,controls=service
    target=option_target(database)
    original=controls._selections._artifacts.load_record
    controls._selections._artifacts.load_record=lambda *a:NS(manifest=original(*a).manifest,artifacts=[])
    value=owner.options(actor=args['actor'],**target)
    assert value['status']=='policy_unavailable' and value['policies']==[]
    with psycopg.connect(database) as db:db.execute('DELETE FROM meta_membership WHERE subject=%s',(args['actor'],))
    with pytest.raises(RuntimeConflict,match='membership'):owner.options(actor=args['actor'],**target)


def test_options_surface_ownership_and_latest_binding(service):
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    owner,args,database,controls=service
    configured=owner.configure(**args)
    options=owner.options(actor=args['actor'],**option_target(database))
    assert {m['definitionId'] for m in options['members']}=={args['definition_id']}
    # A new exact binding is a real original-Owner revision, not an edited row.
    with psycopg.connect(database,row_factory=dict_row) as db:
        db.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",owner.scope.key)
        db.execute('SET LOCAL ROLE aos_runtime')
        schedule=args['members'][0]['scheduleId']
        binding=PipelineScheduleControlOwner.read_latest(db,scope=owner.scope,schedule_id=schedule)
        successor=PipelineScheduleControlOwner(controls=controls).bind(db,scope=owner.scope,schedule_id=schedule,
            control_ref=binding.control_ref,actor=args['actor'],idempotency_key='successor',previous_ref=binding.ref)
    options=owner.options(actor=args['actor'],**option_target(database))
    selected=next(m for m in options['members'] if m['scheduleId']==schedule)
    assert selected['bindingRef']==successor.ref.model_dump(mode='json',by_alias=True,exclude_none=True)
    assert selected['bindingRef']!=binding.ref.model_dump(mode='json',by_alias=True,exclude_none=True)
    assert owner.read(definition_id=args['definition_id'],actor=args['actor'])==configured


def test_options_reject_unknown_generation(service):
    from uuid import uuid4
    owner,args,database,_=service
    target=option_target(database);target['generation']=str(uuid4())
    with pytest.raises(LookupError,match='generation'):owner.options(actor=args['actor'],**target)


def test_options_never_fall_back_to_old_generation_binding(service):
    """Query regression only: second runtime is a named disabled/fenced fixture."""
    from uuid import uuid4
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft, PipelineRuntimeControlDraft
    owner,args,database,controls=service
    target=option_target(database)
    generation=str(uuid4())
    schedule=args['members'][0]['scheduleId']
    with psycopg.connect(database,row_factory=dict_row) as db:
        # Explicit lifecycle fixture, not a claim that reinstall was executed.
        db.execute('''INSERT INTO extension_runtime_binding
            (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
             profile_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,config_ref)
            SELECT org_id,project_id,installation_id,%s,installation_revision,package_lock_ref,
                profile_ref,execution_epoch,'disabled','ready',false,true,config_ref
            FROM extension_runtime_binding WHERE installation_id=%s AND generation=%s''',
            (generation,target['installation_id'],target['generation']))
        db.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",owner.scope.key)
        db.execute('SET LOCAL ROLE aos_runtime')
        binding=PipelineScheduleControlOwner.read_latest(db,scope=owner.scope,schedule_id=schedule)
        draft=controls.run_current(db,scope=owner.scope,ref=binding.control_ref,actor=args['actor'],execute=lambda d,s:d)
        selected=PipelineSourceSelectionDraft.model_validate(dict(
            draft.model_dump(exclude={'schema_version','source_selection_ref'}),generation=generation))
        selection=controls._selections.append(db,draft=selected,actor=args['actor'],idempotency_key='second-gen-selection')
        control=controls.append(db,draft=PipelineRuntimeControlDraft.model_validate(dict(
            selected.model_dump(exclude={'schema_version'}),source_selection_ref=selection)),
            actor=args['actor'],idempotency_key='second-gen-control')
        successor=PipelineScheduleControlOwner(controls=controls).bind(db,scope=owner.scope,schedule_id=schedule,
            control_ref=control,actor=args['actor'],idempotency_key='second-gen-binding',previous_ref=binding.ref)
        assert successor.generation==generation and successor.ref.revision==binding.ref.revision+1
    options=owner.options(actor=args['actor'],**target)
    assert options['status']=='incomplete'
    assert options['missing']==[binding.pipeline_id]
    assert options['members']==[] and options['policies']==[]
    with psycopg.connect(database) as db:
        assert db.execute('SELECT count(*) FROM pipeline_schedule_control_binding WHERE schedule_id=%s',(schedule,)).fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM meta_schedule_run').fetchone()[0]==0
