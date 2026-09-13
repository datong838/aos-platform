"""Real SQL routing semantics in temporary relations, not an authorization fixture."""
from datetime import datetime,timedelta,timezone
from uuid import UUID
import pytest
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row
from test_lifecycle_pg import database,pytestmark
from aos_api.ecommerce_product_event_discovery import _query_candidates
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project');INSTALL=UUID(int=1);GEN=UUID(int=2);SEL=UUID(int=3);CONTROL=UUID(int=4)


@pytest.fixture
def discovery(database):
    conn,_,_=database
    conn.row_factory=dict_row
    conn.execute('''CREATE TABLE ecommerce_investigation_schedule_policy_head(org_id text,project_id text,schedule_policy_id text,current_revision bigint,authority_data jsonb);
CREATE TABLE automation_schedule_binding(org_id text,project_id text,policy_id text,policy_revision bigint,policy_hash text,installation_id uuid,generation uuid,cadence text,enabled boolean,approved boolean,effective_from timestamptz,effective_until timestamptz);
CREATE TABLE pipeline_source_selection_revision(org_id text,project_id text,installation_id uuid,generation uuid,selection_id uuid,revision bigint,content_hash text,pipeline_id text);
CREATE TABLE pipeline_controlled_source_claim(org_id text,project_id text,installation_id uuid,generation uuid,pipeline_id text,run_id text,actor text);
CREATE TABLE meta_schedule_run(org_id text,project_id text,id text,schedule_id text,status text,executor_stopped boolean,executor_id text,finished_at timestamptz);
CREATE TABLE meta_schedule(org_id text,project_id text,id text,pipeline_id text,enabled boolean,ingest jsonb);
CREATE TABLE pipeline_schedule_control_binding(org_id text,project_id text,schedule_id text,pipeline_id text,installation_id uuid,generation uuid,actor text,revision bigint,control_id uuid,control_revision bigint,control_hash text);
CREATE TABLE ecommerce_ingress_command(org_id text,project_id text,run_id text);
CREATE TABLE ecommerce_ingress_derived_command(org_id text,project_id text,run_id text);
CREATE TABLE ecommerce_ingress_dataset_receipt(org_id text,project_id text,run_id text);''')
    now=datetime.now(timezone.utc)
    auth=dict(schemaVersion='aos.ecommerce.product-event-schedule-policy/v1',contentHash='sha256:'+'a'*64,
        sourceSelectionRef=dict(resourceId='source-selection-'+str(SEL),revision=1,contentHash='sha256:'+'b'*64))
    conn.execute('INSERT INTO ecommerce_investigation_schedule_policy_head VALUES(%s,%s,%s,1,%s)',(*SCOPE.key,'policy',Jsonb(auth)))
    conn.execute("INSERT INTO automation_schedule_binding VALUES(%s,%s,'policy',1,%s,%s,%s,'event',true,true,%s,%s)",
        (*SCOPE.key,auth['contentHash'],INSTALL,GEN,now-timedelta(hours=1),now+timedelta(hours=1)))
    conn.execute("INSERT INTO pipeline_source_selection_revision VALUES(%s,%s,%s,%s,%s,1,%s,'pipeline')",(*SCOPE.key,INSTALL,GEN,SEL,'sha256:'+'b'*64))
    conn.execute("INSERT INTO meta_schedule VALUES(%s,%s,'schedule','pipeline',true,%s)",(*SCOPE.key,Jsonb(dict(kind='pipeline-live-v1',pipelineId='pipeline'))))
    conn.execute("INSERT INTO pipeline_schedule_control_binding VALUES(%s,%s,'schedule','pipeline',%s,%s,'actor',1,%s,1,%s)",(*SCOPE.key,INSTALL,GEN,CONTROL,'sha256:'+'c'*64))
    def insert(run):
        conn.execute("INSERT INTO pipeline_controlled_source_claim VALUES(%s,%s,%s,%s,'pipeline',%s,'actor')",(*SCOPE.key,INSTALL,GEN,run))
        conn.execute("INSERT INTO meta_schedule_run VALUES(%s,%s,%s,'schedule','succeeded',true,'ec-live-v1',%s)",(*SCOPE.key,run,now))
        for table in ('ecommerce_ingress_command','ecommerce_ingress_derived_command','ecommerce_ingress_dataset_receipt'):
            from psycopg import sql
            conn.execute(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s)').format(sql.Identifier(table)),(*SCOPE.key,run))
    insert('run-1');insert('run-2')
    return conn,insert


def read(conn,**kw):return _query_candidates(conn,SCOPE,INSTALL,GEN,**kw)


def test_paging_wrap_discovers_late_smaller_key(discovery):
    conn,insert=discovery
    first=read(conn,limit=1);assert first[0]['runId']=='run-1'
    second=read(conn,after=('policy','run-1'),limit=1);assert second[0]['runId']=='run-2'
    assert read(conn,after=('policy','run-2'))==()
    insert('run-0')
    assert read(conn,limit=1)[0]['runId']=='run-0'
    assert set(first[0])=={'policyId','runId','actor','controlRef'}


def test_current_control_successor_is_used(discovery):
    conn,_=discovery
    conn.execute('INSERT INTO pipeline_schedule_control_binding SELECT org_id,project_id,schedule_id,pipeline_id,installation_id,generation,actor,2,control_id,2,control_hash FROM pipeline_schedule_control_binding')
    assert all(row['controlRef']['revision']==2 for row in read(conn))
    conn.execute('UPDATE pipeline_schedule_control_binding SET generation=%s WHERE revision=2',(UUID(int=99),))
    assert read(conn)==()


@pytest.mark.parametrize('fault',['disabled','unfinished','receipt','source_hash','actor','generation','tenant'])
def test_ineligible_routes_are_excluded(discovery,fault):
    conn,_=discovery
    if fault=='disabled':conn.execute('UPDATE automation_schedule_binding SET enabled=false')
    if fault=='unfinished':conn.execute("UPDATE meta_schedule_run SET status='running'")
    if fault=='receipt':conn.execute('DELETE FROM ecommerce_ingress_dataset_receipt')
    if fault=='source_hash':conn.execute("UPDATE pipeline_source_selection_revision SET content_hash='bad'")
    if fault=='actor':conn.execute("UPDATE pipeline_schedule_control_binding SET actor='other'")
    if fault=='generation':conn.execute('UPDATE pipeline_controlled_source_claim SET generation=%s',(UUID(int=99),))
    if fault=='tenant':conn.execute("UPDATE pipeline_controlled_source_claim SET org_id='dev-org'")
    assert read(conn)==()


def test_discovery_bounds_rejected_before_query():
    for limit in (True,0,101):
        with pytest.raises(ValueError):_query_candidates(None,SCOPE,INSTALL,GEN,limit=limit)


def test_public_discovery_rejects_owner_connection(discovery):
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_product_event_discovery import discover_event_candidates
    conn,_=discovery
    with pytest.raises(PermissionError):discover_event_candidates(HostTransaction(conn),SCOPE,INSTALL,GEN)


def test_exact_origin_is_filtered_before_page_limit(discovery):
    conn,_=discovery
    assert [row['runId'] for row in read(conn,exact=('policy','run-2','actor'),limit=1)]==['run-2']
    for exact in [('policy','missing','actor'),('policy','run-2','other'),('other','run-2','actor')]:
        assert read(conn,exact=exact,limit=1)==()


def test_claim_origin_routes_only_original_current_batch(discovery,monkeypatch):
    from aos_api import ecommerce_product_event_discovery as module
    from aos_api.automation_occurrence_store import ClaimedOccurrence
    from types import SimpleNamespace
    conn,_=discovery
    # Origin read is a named double; its real RLS/hash coverage lives in origin_pg.
    origin={'runId':'run-2','actor':'actor'}
    monkeypatch.setattr(module,'ProductEventOriginStore',lambda *args:SimpleNamespace(read=lambda occurrence_id:origin))
    claimed=ClaimedOccurrence(UUID(int=11),'policy',1,'ecommerce_growth_analysis_advance',INSTALL,GEN,3,
                             'worker',datetime.now(timezone.utc),UUID(int=12),'key')
    assert module.discover_claim_origin(conn,SCOPE,claimed)['runId']=='run-2'
    origin['actor']='other'
    with pytest.raises(PermissionError):module.discover_claim_origin(conn,SCOPE,claimed)
