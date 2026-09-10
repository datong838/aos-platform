import os
import json
import hashlib
import time
import pytest
from test_aip_budget_reservation_pg import database,runtime_connection
from aos_api import ecom_projector as projector
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


def test_pending_counts_unleased_rows_and_excludes_other_tenant(database,monkeypatch):
    database.owner.execute('CREATE TABLE projection_outbox(outbox_id integer PRIMARY KEY,org_id text,project_id text,input_revision bigint,event_source text,projected boolean,payload jsonb,payload_hash text,projected_at timestamptz,projection_error text)')
    database.owner.execute('CREATE TABLE meta_object_type(id text PRIMARY KEY,name text,description text,published boolean,properties jsonb)')
    database.owner.execute('CREATE TABLE obj_instance(org_id text,project_id text,object_type text,object_id text,props jsonb,PRIMARY KEY(org_id,project_id,object_type,object_id))')
    for table in ('projection_outbox','obj_instance','meta_object_type'):
        database.owner.execute(f'GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime')
    for table in ('projection_outbox','obj_instance'):
        database.owner.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        database.owner.execute(f"CREATE POLICY tenant_scope ON {table} TO aos_runtime USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    for index,org in ((1,'org-org'),(2,'org-org'),(3,'dev-org')):
        payload={'schemaVersion':1,'entityKind':'object','record':{'objectType':'Shop','identity':{'externalId':str(index)},'sourceUpdatedAt':'2026-09-11T00:00:00Z','properties':{'name':'fixture'}}}
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        database.owner.execute("INSERT INTO projection_outbox VALUES(%s,%s,'dev-project',%s,'authoritative_store',false,%s::jsonb,%s,NULL,NULL)",(index,org,index,raw,hashlib.sha256(raw.encode()).hexdigest()))
    monkeypatch.setattr(projector,'connect',runtime_connection(database))
    scope=TenantScope('org-org','dev-project')
    assert projector.project_pending(scope,limit=1)=={'projected':1,'pending':1}
    with database.owner.transaction():
        database.owner.execute('SELECT * FROM projection_outbox WHERE outbox_id=2 FOR UPDATE')
        assert projector.project_pending(scope,limit=1)=={'projected':0,'pending':1}
    assert projector.project_until_caught_up(scope,deadline=time.monotonic()+5)=={'projected':1,'pending':0}
    assert database.owner.execute('SELECT projected FROM projection_outbox WHERE outbox_id=3').fetchone()['projected'] is False
    assert database.owner.execute('SELECT count(*) AS n FROM obj_instance').fetchone()['n']==2
