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
