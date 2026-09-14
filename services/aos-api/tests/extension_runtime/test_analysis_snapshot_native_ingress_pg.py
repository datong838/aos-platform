"""Real native input commits in per-test databases; source/assets are named.

Reuse the original database bootstrap, not a reduced schema or expanded grants.
No application Task transaction is committed by this input-only test fixture.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest
from sqlalchemy import create_engine, event

from tests.conftest import _isolated_postgres_database
from test_product_event_write_pg import stored as original_stored
from test_analysis_snapshot_native_claims_pg import (
    native_claims_case, host_case, control_governed, governed, service_case, pair, body,
)
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.pipeline_selected_snapshot_group import SelectedSnapshotGroupResult
import aos_api.pipeline_controlled_snapshot_group_ingress as module


@pytest.fixture
def private_database(monkeypatch):
    parent = os.environ['AOS_DATABASE_URL']
    assert os.environ.get('AOS_TEST_USE_SHARED_DATABASE') != '1'
    with psycopg.connect(parent) as conn:
        assert conn.info.dbname.endswith('_ti4_test')
    # These two boot guards are process-scoped, not database-scoped. Reset only
    # the documented flags while invoking the original bootstrap for a new DB.
    # monkeypatch restores the parent flags after this fixture is torn down.
    from aos_api import tenant_catalog, data_os_store
    monkeypatch.setattr(tenant_catalog,'_schema_ready',False)
    monkeypatch.setattr(data_os_store,'_schema_ready',False)
    generator = _isolated_postgres_database.__wrapped__()
    next(generator)
    try:
        private = os.environ['AOS_DATABASE_URL']
        assert private != parent
        yield private
    finally:
        generator.close()
        assert os.environ['AOS_DATABASE_URL'] == parent


@pytest.fixture
def stored(private_database,pair,request):
    yield from original_stored.__wrapped__(pair,request)


def complete_named_installation_draft(conn,scope):
    """Complete the rollback-only Host fixture's draft; never claim activation.

Its old parent-only insert cannot COMMIT under the real deferred FK. Supply
the canonical empty lock, draft revision and matching event, keeping every
original trigger active. Installed runtime/asset authority remains named.
"""
    from tests.asset_registry.test_composition_installation_migration import _lock_documents
    conn.execute('RESET ROLE')
    installation = conn.execute('SELECT installation_pk FROM bundle_installation').fetchone()['installation_pk']
    composition = uuid4()
    diff,lock = _lock_documents()
    def digest(value):
        return conn.execute('SELECT canonical_bundle_control_sha256(%s::jsonb) AS hash',
                            (Jsonb(value),)).fetchone()['hash']
    request = dict(requested=[])
    registry = dict(schemaVersion='aos.dev/registry-snapshot/v1alpha1',candidates=[])
    lock['request'] = request
    lock['registrySnapshotHash'] = digest(registry)
    lock_hash,diff_hash = digest(lock),digest(diff)
    conn.execute('''INSERT INTO bundle_composition(org_id,project_id,composition_pk,composition_id,
        request_json,request_hash,registry_snapshot_json,registry_snapshot_hash,resolver_version,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'aos-resolver/1.0.0','fixture')''',
        (*scope.key,composition,uuid4(),Jsonb(request),digest(request),Jsonb(registry),digest(registry)))
    conn.execute('''INSERT INTO bundle_composition_lock(org_id,project_id,composition_pk,revision,
        lock_payload,lock_hash,permission_diff_json,permission_diff_hash,migration_plan_json,migration_plan_hash,
        contribution_diff_json,contribution_diff_hash,created_by)
        VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,'fixture')''',
        (*scope.key,composition,Jsonb(lock),lock_hash,Jsonb(diff),diff_hash,Jsonb(diff),diff_hash,Jsonb(diff),diff_hash))
    conn.execute('''INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,revision,
        state,composition_pk,lock_revision,lock_hash,permission_diff_hash,migration_plan_hash,
        contribution_diff_hash,overlay_revision,requested_by)
        VALUES(%s,%s,%s,1,'draft',%s,1,%s,%s,%s,%s,'native-test-draft','fixture')''',
        (*scope.key,installation,composition,lock_hash,diff_hash,diff_hash,diff_hash))
    conn.execute('''INSERT INTO bundle_installation_event(org_id,project_id,installation_pk,sequence,
        from_revision,to_revision,from_state,to_state,actor)
        VALUES(%s,%s,%s,1,NULL,1,NULL,'draft','fixture')''', (*scope.key,installation))
    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')


@pytest.fixture
def native_input_case(native_claims_case,private_database,monkeypatch):
    conn,groups,args,_,_ = native_claims_case
    database = conn.info.dbname
    plans = {}
    with conn.transaction():
        groups._groups.run_current(conn,scope=args['scope'],refs=tuple(ref for ref,_ in args['bindings']),
            actor=args['actor'],execute=lambda group:plans.update({draft.pipeline_id:plan for _,draft,plan in group.members}))
    # Installation and source setup may commit only before any Task exists.
    for table in ('aip_task','aip_task_run','ecommerce_investigation_run'):
        assert conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] == 0
    complete_named_installation_draft(conn,args['scope'])
    conn.commit()
    conn.autocommit = True
    state = dict(calls=0)
    def named_assets(db,draft,actor,consume,*,snapshot=False):
        assert db.info.dbname == database and actor == args['actor']
        plan = plans[draft.pipeline_id]
        return consume(plan if snapshot else plan.read_spec)
    claims = groups._claims
    claims._controls._selections._guarded = named_assets
    @contextmanager
    def connect():
        with psycopg.connect(private_database,autocommit=True,row_factory=dict_row) as db:
            assert db.info.dbname == database
            db.execute('SET SESSION AUTHORIZATION aos_runtime')
            yield db
    engine = create_engine(private_database.replace('postgresql://','postgresql+psycopg://',1))
    @event.listens_for(engine,'connect')
    def runtime_identity(dbapi_conn,record):
        dbapi_conn.execute('SET SESSION AUTHORIZATION aos_runtime')
        dbapi_conn.commit()
    store = EcomConsistencyStore(engine)
    def source(**kwargs):
        state['calls'] += 1
        # A separate connection sees the committed group, before any source call.
        with connect() as proof, proof.transaction():
            proof.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",args['scope'].key)
            assert proof.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 12
            assert proof.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n'] == 1
        now = datetime.now(timezone.utc)
        group = kwargs['group']
        rows = {plan.read_spec.table:[dict(site_id=1,site_name='native named source')]
                for _,_,plan in group.members}
        return SelectedSnapshotGroupResult(rows,group.members[0][1].source_configuration_ref,now,now)
    monkeypatch.setattr(module,'read_selected_snapshot_group',source)
    executor = module.ControlledSnapshotGroupIngress(claims=claims,store=store,connect=connect)
    try:
        yield executor,conn,args,state
    finally:
        engine.dispose()


@pytest.mark.parametrize('lost_ack',[False,True])
def test_native_input_commit_and_replay(native_input_case,monkeypatch,lost_ack):
    executor,conn,args,state = native_input_case
    original = executor._transaction
    count = 0
    @contextmanager
    def interrupt(scope):
        nonlocal count
        with original(scope) as db:
            yield db
        count += 1
        if count == 2:
            raise RuntimeError('native input acknowledgement lost')
    if lost_ack:
        monkeypatch.setattr(executor,'_transaction',interrupt)
        with pytest.raises(RuntimeError,match='acknowledgement lost'):
            executor.prepare(**args)
        monkeypatch.setattr(executor,'_transaction',original)
    else:
        first = executor.prepare(**args)
        assert not first.replayed and first.rows_read == 12
    again = executor.prepare(**args)
    assert again.replayed and again.rows_read == 0 and len(again.parents) == 12
    assert state['calls'] == 1
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n'] == 12
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM ecom_object').fetchone()['n'] == 0


@pytest.mark.parametrize('failure',['claim-ack','partial-input'])
def test_native_uncertain_input_never_reissues(native_input_case,monkeypatch,failure):
    executor,conn,args,state = native_input_case
    original = executor._transaction
    @contextmanager
    def uncertain(scope):
        with original(scope) as db:
            yield db
        raise RuntimeError('native claim acknowledgement lost')
    saved = module.ControlledIngressJournal.save_for_running_schedule
    count = 0
    def partial(self,*a,**kw):
        nonlocal count
        count += 1
        if count == 6:
            raise RuntimeError('native sixth input failed')
        return saved(self,*a,**kw)
    if failure == 'claim-ack':
        monkeypatch.setattr(executor,'_transaction',uncertain)
    else:
        monkeypatch.setattr(module.ControlledIngressJournal,'save_for_running_schedule',partial)
    with pytest.raises(RuntimeError,match='native'):
        executor.prepare(**args)
    assert state['calls'] == (0 if failure == 'claim-ack' else 1)
    if failure == 'partial-input':
        assert count == 6
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n'] == 0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n'] == 0
    monkeypatch.setattr(executor,'_transaction',original)
    monkeypatch.setattr(module.ControlledIngressJournal,'save_for_running_schedule',saved)
    before = state['calls']
    with pytest.raises(IngressJournalConflict,match='GROUP_OUTCOME_UNCONFIRMED'):
        executor.prepare(**args)
    assert state['calls'] == before
