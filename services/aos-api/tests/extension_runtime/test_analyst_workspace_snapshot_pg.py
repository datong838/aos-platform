import os
from copy import deepcopy
import pytest
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from test_lifecycle_pg import database
from test_analyst_workspace_view import snapshot, projector
from aos_api.extension_runtime.analyst_workspace_snapshot import read_analyst_workspace_snapshot
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


def test_snapshot_uses_one_pg_view_and_excludes_foreign_scope(database,monkeypatch,projector):
    conn,_,schema=database
    from psycopg.rows import dict_row
    conn.row_factory=dict_row
    monkeypatch.delenv('AOS_OPENFGA_API_URL',raising=False)
    for statement in [
        'CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text)',
        'CREATE TABLE authz_tuple(org_id text,project_id text,user_key text,relation text,object_key text)',
        'CREATE TABLE ecommerce_investigation_case_head(org_id text,project_id text,case_id text,current_revision int,updated_at timestamptz)',
        'CREATE TABLE ecommerce_investigation_case_revision(org_id text,project_id text,case_id text,revision int,authority_data jsonb)',
        'CREATE TABLE ecommerce_investigation_run(org_id text,project_id text,case_id text,run_id text,created_at timestamptz,authority_data jsonb)',
        'CREATE TABLE ecommerce_investigation_run_state_head(org_id text,project_id text,run_id text,authority_data jsonb)',
    ]:conn.execute(statement)
    conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','reader','operator')")
    value=snapshot()['cases'][0];case=value['case'];run=value['runs'][0]['authority'];state=value['runs'][0]['state']
    def insert_case(c,identity,org='org-org'):
        payload=deepcopy(case);payload['caseId']=identity
        if payload['priorRef']:payload['priorRef']['resourceId']=identity
        import hashlib,json
        payload['contentHash']='sha256:'+hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k!='contentHash'},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        c.execute('INSERT INTO ecommerce_investigation_case_head VALUES(%s,%s,%s,%s,now())',(org,'dev-project',identity,case['revision']))
        c.execute('INSERT INTO ecommerce_investigation_case_revision VALUES(%s,%s,%s,%s,%s)',(org,'dev-project',identity,case['revision'],Jsonb(payload)))
    insert_case(conn,case['caseId']);insert_case(conn,'foreign-case','dev-org')
    conn.execute('INSERT INTO ecommerce_investigation_run VALUES(%s,%s,%s,%s,now(),%s)',('org-org','dev-project',case['caseId'],run['runId'],Jsonb(run)))
    conn.execute('INSERT INTO ecommerce_investigation_run_state_head VALUES(%s,%s,%s,%s)',('org-org','dev-project',run['runId'],Jsonb(state)))
    def read():return read_analyst_workspace_snapshot(conn=conn,scope=TenantScope('org-org','dev-project'),subject='reader',required_markings=())
    def begin():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
    with conn.transaction():
        begin();first=read()
        assert projector(first)['caseCount']==1 and projector(first)['runCount']==1
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
            other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            insert_case(other,'case-later')
        assert len(read()['cases'])==1
    with conn.transaction():
        begin();assert len(read()['cases'])==2
