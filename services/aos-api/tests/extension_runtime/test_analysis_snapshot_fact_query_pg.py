"""Actual Query/Evidence/Store, original DDL; named upstream and namespace adapters."""
import ast
import importlib.util
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_analysis_snapshot_source_evidence_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,prepared_case,
    assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,fact_case,evidence_case,revoke,
)
from aos_api.ecommerce_analysis_snapshot_fact_query import AnalysisSnapshotFactQuery


@pytest.fixture
def query_case(evidence_case,business_case,monkeypatch):
    conn,state,source,call=evidence_case
    pending=business_case[2]
    pending['requirement']['expiresAt']=(datetime.now().astimezone()+timedelta(hours=1)).isoformat()
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    conn.execute('RESET ROLE')
    tree=ast.parse((root/'aip4_001_eval_lineage_observability_contract.py').read_text())
    ddl=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)
        and n.value.strip().startswith('CREATE TABLE aip_metric_definition_revision ('))
    conn.execute(ddl)
    scope=source.analysis.scope
    conn.execute('INSERT INTO twa_org(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING',(scope.org_id,'fixture'))
    conn.execute('INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(*scope.key,'fixture'))
    conn.execute('GRANT SELECT,INSERT ON aip_metric_definition_revision TO aos_runtime')
    spec=importlib.util.spec_from_file_location('query_ddl',root/'aip8_001_analyst_query_authority.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    import aos_api.ecommerce_analysis_snapshot_fact_query as query_module
    class NamespaceConnection:
        def execute(self,statement,params=()):
            return conn.execute(statement.replace('public.',f'"{source._schema}".'),params)
    monkeypatch.setattr(query_module,'HostTransaction',lambda db:HostTransaction(NamespaceConnection()))
    return conn,state,source,AnalysisSnapshotFactQuery(source),call,pending


def test_fixed_counts_and_idempotent_complete_source(query_case):
    conn,state,source,query,call,pending=query_case
    evidence=source.capture_current(conn,**call)
    ref=query.execute_current(conn,evidence_ref=evidence)
    assert query.execute_current(conn,evidence_ref=evidence)==ref
    result=query.read_current(conn,result_ref=ref,evidence_ref=evidence)
    assert [row.row_id for row in result.rows]==['Shop','Weapp']
    assert result.rows[0].values['observedCount']==1
    assert len(result.source_refs)==1 and result.source_refs[0].ref.resource_id==evidence.resource_id
    assert result.status.value=='partial' and result.confidence.score is None
    assert conn.execute('SELECT count(*) AS n FROM aip_analyst_query_job').fetchone()['n']==1
    assert state['calls']==1


@pytest.mark.parametrize('fault',['revoked','policy','expired'])
def test_current_source_required_for_query(query_case,fault):
    conn,state,source,query,call,pending=query_case
    if fault=='expired':pending['requirement']['expiresAt']=(datetime.now().astimezone()-timedelta(seconds=1)).isoformat()
    evidence=source.capture_current(conn,**call)
    if fault=='revoked':revoke(conn,source,evidence)
    if fault=='policy':state['field_raw']=b'{}'
    with pytest.raises((ValueError,PermissionError)):
        query.execute_current(conn,evidence_ref=evidence)
    assert conn.execute('SELECT count(*) AS n FROM aip_analyst_query_job').fetchone()['n']==0


def test_query_write_rolls_back_if_source_changes_after_record(query_case,monkeypatch):
    conn,state,source,query,call,_=query_case;evidence=source.capture_current(conn,**call)
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    original=AipAnalystQueryStore.record_result
    def record(self,*args,**kwargs):
        result=original(self,*args,**kwargs);state['field_raw']=b'{}';return result
    monkeypatch.setattr(AipAnalystQueryStore,'record_result',record)
    with pytest.raises(ValueError):query.execute_current(conn,evidence_ref=evidence)
    assert conn.execute('SELECT count(*) AS n FROM aip_analyst_query_job').fetchone()['n']==0


def test_revocation_invalidates_existing_query_read_and_replay(query_case):
    conn,_,source,query,call,_=query_case;evidence=source.capture_current(conn,**call)
    ref=query.execute_current(conn,evidence_ref=evidence)
    revoke(conn,source,evidence)
    with pytest.raises(ValueError):query.read_current(conn,result_ref=ref,evidence_ref=evidence)
    with pytest.raises(ValueError):query.execute_current(conn,evidence_ref=evidence)
    assert conn.execute('SELECT count(*) AS n FROM aip_analyst_query_job').fetchone()['n']==1


def test_canary_cannot_consume_positive_query(query_case):
    conn,_,source,query,call,_=query_case;evidence=source.capture_current(conn,**call)
    ref=query.execute_current(conn,evidence_ref=evidence)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
        with pytest.raises((LookupError,PermissionError)):
            query.read_current(conn,result_ref=ref,evidence_ref=evidence)


@pytest.mark.parametrize('field',['validCount','confidence'])
def test_rehashed_forged_result_is_not_a_fixed_query(query_case,field):
    """Owner-only corruption of isolated test table; production append-only stays intact."""
    from aos_api.aip_analyst_contracts import QueryResultRevision
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    from psycopg.types.json import Jsonb
    conn,_,source,query,call,_=query_case;evidence=source.capture_current(conn,**call)
    ref=query.execute_current(conn,evidence_ref=evidence)
    body=conn.execute('SELECT result_json FROM aip_analyst_query_result_revision').fetchone()['result_json']
    request=conn.execute('SELECT request_json FROM aip_analyst_query_job').fetchone()['request_json']
    if field=='validCount':body['rows'][0]['values']['validCount']=123
    else:body['confidence']['basis']=['forged confidence']
    forged=QueryResultRevision.model_validate(body)
    body['contentHash']=AipAnalystQueryStore._result_hash(source.analysis.scope,request,forged)
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE aip_analyst_query_result_revision DISABLE TRIGGER USER')
    conn.execute('UPDATE aip_analyst_query_result_revision SET result_json=%s,content_hash=%s',(Jsonb(body),body['contentHash']))
    conn.execute('ALTER TABLE aip_analyst_query_result_revision ENABLE TRIGGER USER')
    conn.execute('SET ROLE aos_runtime')
    ref=ref.model_copy(update={'content_hash':'sha256:'+body['contentHash']})
    with pytest.raises(ValueError):query.read_current(conn,result_ref=ref,evidence_ref=evidence)


@pytest.mark.parametrize('name',[
    'test_store_idempotency_cas_result_and_tenant_isolation',
    'test_idempotency_payload_drift_is_rejected',
    'test_cancel_timeout_and_reconcile_are_append_only_terminal_facts',
])
def test_original_query_store_regression_with_select_insert_only(query_case,monkeypatch,name):
    from contextlib import contextmanager
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    conn,_,source,_,_,_=query_case
    test_path=Path(__file__).resolve().parents[1]/'aip/test_aip8_query_store.py'
    spec=importlib.util.spec_from_file_location('original_query_tests',test_path)
    original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    class NamespaceConnection:
        def execute(self,statement,params=()):
            return conn.execute(statement.replace('public.',f'"{source._schema}".'),params)
        def commit(self):pass  # outer context owns the actual transaction
    @contextmanager
    def connect(scope):
        with conn.transaction():
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            yield NamespaceConnection()
    monkeypatch.setattr(original,'connect',connect)
    monkeypatch.setattr(original,'AipAnalystQueryStore',lambda:AipAnalystQueryStore(connect_factory=connect))
    assert not conn.execute("SELECT has_table_privilege('aos_runtime','aip_analyst_query_event','UPDATE') AS allowed").fetchone()['allowed']
    getattr(original,name)()


def test_original_query_transition_lock_serializes_two_connections(query_case):
    import psycopg
    from psycopg.rows import dict_row
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    conn,_,source,query,call,_=query_case
    evidence=source.capture_current(conn,**call);ref=query.execute_current(conn,evidence_ref=evidence)
    store=AipAnalystQueryStore()
    class NamespaceConnection:
        def __init__(self,db):self.db=db
        def execute(self,statement,params=()):
            return self.db.execute(statement.replace('public.',f'"{source._schema}".'),params)
    with psycopg.connect(conn.info.dsn,autocommit=True,row_factory=dict_row) as other:
        other.execute('SET ROLE aos_runtime')
        with conn.transaction():
            store._latest_for_update(NamespaceConnection(conn),source.analysis.scope,ref.resource_id)
            with pytest.raises(psycopg.errors.LockNotAvailable),other.transaction():
                other.execute("SET LOCAL lock_timeout='100ms'")
                other.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",source.analysis.scope.key)
                store._latest_for_update(NamespaceConnection(other),source.analysis.scope,ref.resource_id)
        with other.transaction():
            other.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",source.analysis.scope.key)
            assert store._latest_for_update(NamespaceConnection(other),source.analysis.scope,ref.resource_id)['sequence']==2
