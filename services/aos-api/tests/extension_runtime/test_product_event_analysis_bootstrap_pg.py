"""Formal event handle with actual stores; installed computation/readiness are explicit fixtures."""
import asyncio
from contextlib import contextmanager
import pytest
from test_analysis_bootstrap_action_pg import (
    review_identity,preview_case,compilation_case,publications,context_publication,context_case,
    startup_case,analysis_case,consumer_case,host_case,control_governed,governed,service_case,stored,pair,body,
)
from test_product_event_analysis_port import command
from aos_api.ecommerce_growth_host_ports import LockedEcommerceGrowthHostPort
_ORIGINAL_DISPATCH_LOCK = LockedEcommerceGrowthHostPort._lock_and_revalidate

pytestmark=[pytest.mark.parametrize('startup_case',['defer-host'],indirect=True),
            pytest.mark.parametrize('stored',['qualified-runtime'],indirect=True)]


@pytest.fixture
def formal_case(preview_case,review_identity,monkeypatch,request):
    conn,analysis,claimed,run_ref,blueprint=preview_case
    assert run_ref is None
    from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog, INITIAL_STORE_PROFILE, INITIAL_STORE_SCOPE
    monkeypatch.setattr(EcommerceInvestigationProfileCatalog,'read',lambda self,kind:(INITIAL_STORE_PROFILE,INITIAL_STORE_SCOPE) if kind==INITIAL_STORE_PROFILE.analysis_type else None)
    monkeypatch.setattr(LockedEcommerceGrowthHostPort,'_lock_and_revalidate',staticmethod(_ORIGINAL_DISPATCH_LOCK))
    from uuid import uuid4
    from psycopg import sql
    identity='fixture_bootstrap_runtime_'+uuid4().hex
    conn.execute('RESET ROLE')
    # The real installer must supply the internal definition; the legacy global
    # review fixture must not accidentally make this formal path succeed.
    conn.execute("DELETE FROM meta_action_type WHERE id='ecommerce_analysis_bootstrap'")
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    for operation in ECOMMERCE_GROWTH_OPERATIONS:
        conn.execute("""INSERT INTO extension_operation_dispatch_binding
            SELECT (jsonb_populate_record(NULL::extension_operation_dispatch_binding,
                to_jsonb(d)||jsonb_build_object('operation_id',%s::text))).*
            FROM extension_operation_dispatch_binding d WHERE org_id=%s AND project_id=%s
              AND operation_id='ecommerce_growth_schedule_trigger' ON CONFLICT DO NOTHING""",(operation,*analysis.scope.key))
    mode=getattr(request,'param','complete10')
    if mode=='legacy9':conn.execute("DELETE FROM extension_operation_dispatch_binding WHERE operation_id='ecommerce_growth_event_control'")
    elif mode=='missing':conn.execute("DELETE FROM extension_operation_dispatch_binding WHERE operation_id='ecommerce_growth_content_review'")
    elif mode=='unknown':conn.execute("UPDATE extension_operation_dispatch_binding SET operation_id='fixture_unknown_operation' WHERE operation_id='ecommerce_growth_event_control'")
    conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT').format(sql.Identifier(identity)))
    conn.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(identity)))
    conn.execute(sql.SQL('SET LOCAL SESSION AUTHORIZATION {}').format(sql.Identifier(identity)))
    conn.execute('SET LOCAL ROLE aos_runtime')
    class Connection:
        def __getattr__(self,name):return getattr(conn,name)
        def commit(self):pass # The fixture retains the real outer transaction.
    @contextmanager
    def connect(scope):
        assert scope==analysis.scope
        yield Connection()
    class InstalledComputation:
        async def build_start(self,request):return command(request)
        async def build_compilation_blueprint(self,profile):return blueprint
    analysis.connect=connect
    analysis.port=InstalledComputation()
    return conn,analysis,claimed


def test_formal_event_handle_creates_complete_initial_lineage(formal_case):
    conn,analysis,claimed=formal_case
    receipt=asyncio.run(analysis.handle(claimed))
    assert receipt['resourceType']=='AnalysisRuntimeReceipt'
    assert conn.execute("SELECT count(*) AS n FROM meta_action_type WHERE id='ecommerce_analysis_bootstrap'").fetchone()['n']==0
    proposal=conn.execute("SELECT action_type_snapshot FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND action_type_id='ecommerce_analysis_bootstrap'",analysis.scope.key).fetchone()
    assert proposal['action_type_snapshot']['installedActionRef']['resourceType']=='InstalledActionTypeRevision'
    assert asyncio.run(analysis.handle(claimed))==receipt
    journal=conn.execute("SELECT request_hash,response FROM ecommerce_growth_runtime_command_receipt WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'",analysis.scope.key).fetchall()
    assert len(journal)==1 and journal[0]['request_hash']==journal[0]['response']['requestHash']
    rows=conn.execute('SELECT status FROM aip_task_run WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchall()
    assert len(rows)==1 and rows[0]['status']=='paused'
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==1
    assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event a JOIN aip_action_proposal p USING(org_id,project_id,proposal_id) WHERE p.org_id=%s AND p.project_id=%s AND p.action_type_id='ecommerce_analysis_bootstrap'",analysis.scope.key).fetchone()['n']==0


def test_formal_final_host_failure_rolls_back_all_initialization(formal_case,monkeypatch):
    conn,analysis,claimed=formal_case
    def fail(*args,**kwargs):raise RuntimeError('fixture final Host failure')
    monkeypatch.setattr(analysis,'_write',fail)
    with pytest.raises(RuntimeError,match='final Host failure'),conn.transaction():
        asyncio.run(analysis.handle(claimed))
    for table in ('aip_task_run','aip_business_investigation_compile_receipt'):
        assert conn.execute(f'SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


@pytest.mark.parametrize('formal_case',['legacy9','complete10','missing','unknown'],indirect=True)
def test_exact_dispatch_group_membership(formal_case):
    import psycopg
    from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
    conn,analysis,claimed=formal_case
    row=conn.execute("SELECT * FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'",analysis.scope.key).fetchone()
    ref=IssuedDispatchRef(org_id=analysis.scope.org_id,project_id=analysis.scope.project_id,
        operation_id=row['operation_id'],handler_kind=row['handler_kind'],dispatch_revision=row['revision'],
        installation_id=str(row['installation_id']),generation=str(row['generation']),execution_epoch=row['execution_epoch'],
        cutover_group_id=str(row['cutover_group_id']),cutover_group_revision=row['cutover_group_revision'])
    operations={r['operation_id'] for r in conn.execute('SELECT operation_id FROM extension_operation_dispatch_binding').fetchall()}
    broken='fixture_unknown_operation' in operations or 'ecommerce_growth_content_review' not in operations
    if broken:
        with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():_ORIGINAL_DISPATCH_LOCK(conn,analysis.scope,ref)
    else:assert _ORIGINAL_DISPATCH_LOCK(conn,analysis.scope,ref).operation_id=='ecommerce_growth_analysis_advance'


def test_formal_rejects_package_command_hash_drift(formal_case):
    conn,analysis,claimed=formal_case
    original=analysis.port.build_start
    async def drift(request):
        result=await original(request)
        result['requestHash']='sha256:'+'f'*64
        return result
    analysis.port.build_start=drift
    with pytest.raises(ValueError),conn.transaction():
        asyncio.run(analysis.handle(claimed))
    assert conn.execute('SELECT count(*) AS n FROM aip_task_run WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0
