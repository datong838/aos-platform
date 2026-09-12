"""Real PG projection transactions; current journal and receipt evidence are named fakes."""
import hashlib
import json
from uuid import uuid4

import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from test_lifecycle_pg import database,pytestmark
from tests.test_ecom_consistency_store import batch,obj
from aos_api.ecom_core_models import SyncScope,StorageIdentity
from aos_api.ecom_consistency_store import EcomConsistencyStore,ProjectionEventEvidence
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.tenant_scope import TenantScope
import aos_api.pipeline_controlled_projection as module

SCOPE=TenantScope('org-org','dev-project')


@pytest.fixture
def projection_case(database):
    conn,_,_=database
    conn.row_factory=dict_row
    conn.execute('''CREATE TABLE meta_object_type(id text PRIMARY KEY,name text,description text,published boolean,properties jsonb);
        CREATE TABLE obj_instance(org_id text,project_id text,object_type text,object_id text,props jsonb,PRIMARY KEY(org_id,project_id,object_type,object_id));
        CREATE TABLE graph_edge(org_id text,project_id text,src_type text,src_id text,rel text,dst_type text,dst_id text,UNIQUE(org_id,project_id,src_type,src_id,rel,dst_type,dst_id));
        CREATE TABLE projection_outbox(outbox_id bigserial PRIMARY KEY,org_id text,project_id text,input_revision bigint,event_key text UNIQUE,payload_hash text,payload jsonb,event_source text,projected boolean,projected_at timestamptz,projection_error text);''')
    record=obj('Shop','one',identity=StorageIdentity(org_id=SCOPE.org_id,workspace_id=SCOPE.project_id,platform='synthetic',shop_or_marketplace_id='1',external_id='one'))
    command=batch(record,batch_scope=SyncScope(org_id=SCOPE.org_id,workspace_id=SCOPE.project_id,platform='synthetic',shop_or_marketplace_id='1',stream='P01'))
    payload={'schemaVersion':1,'entityKind':'object','changeKind':'objects_written','record':record.model_dump(mode='json')}
    key=hashlib.sha256(b'original').hexdigest()
    digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    conn.execute("INSERT INTO projection_outbox(org_id,project_id,input_revision,event_key,payload_hash,payload,event_source,projected) VALUES(%s,%s,2,%s,%s,%s,'authoritative_store',false)",(*SCOPE.key,key,digest,Jsonb(payload)))
    parent=dict(runId='run',pipelineId='P01',sourceId='source',sourceRevision=str(uuid4()),pipelineHash='a'*64,command=command.model_dump(mode='json'))
    state={'deny':False,'calls':0}
    journal=object.__new__(ControlledIngressJournal)
    def gate(db,scope,*a,**kw):
        assert scope==SCOPE
        state['calls']+=1
        if state['deny']:raise PermissionError('current denied')
    journal.lock_run=gate;journal.verify_running_schedule=gate
    journal.read=lambda *a:parent
    journal.read_derived=lambda *a:{'commands':[]}
    store=object.__new__(EcomConsistencyStore)
    evidence=(ProjectionEventEvidence(key,digest,2,False),)
    store.read_batch_projection_evidence=lambda actual,derived:evidence if actual==command and derived==[] else pytest.fail('original commands differ')
    return conn,journal,store,state,evidence,payload


def execute(case):
    conn,journal,store,*_=case
    with conn.transaction():return module.project_saved_batch(conn,SCOPE,'run',journal=journal,store=store)


def unrelated(case,revision):
    conn,_,_,_,_,payload=case
    payload=json.loads(json.dumps(payload));payload['record']['identity']['externalId']='unrelated'
    key=hashlib.sha256(str(uuid4()).encode()).hexdigest()
    digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    conn.execute("INSERT INTO projection_outbox(org_id,project_id,input_revision,event_key,payload_hash,payload,event_source,projected) VALUES(%s,%s,%s,%s,%s,%s,'authoritative_store',false)",(*SCOPE.key,revision,key,digest,Jsonb(payload)))
    return key


def test_exact_projection_leaves_later_unrelated_event_and_replays_noop(projection_case):
    key=unrelated(projection_case,3)
    assert execute(projection_case)=={'projected':1,'pending':0}
    assert execute(projection_case)=={'projected':0,'pending':0}
    conn,*_=projection_case
    assert conn.execute('SELECT object_id FROM obj_instance').fetchall()==[{'object_id':'one'}]
    assert conn.execute('SELECT projected FROM projection_outbox WHERE event_key=%s',(key,)).fetchone()=={'projected':False}


@pytest.mark.parametrize('case',['earlier','hash','missing','denied','after_write','rollback'])
def test_out_of_scope_or_drifted_projection_leaves_no_writes(projection_case,monkeypatch,case):
    conn,_,_,state,evidence,_=projection_case
    if case=='earlier':unrelated(projection_case,1)
    if case=='hash':conn.execute("UPDATE projection_outbox SET payload_hash=%s",('f'*64,))
    if case=='missing':conn.execute('DELETE FROM projection_outbox')
    if case=='denied':state['deny']=True
    if case=='after_write':
        original=module._project_object
        def write(*args):
            original(*args);state['deny']=True
        monkeypatch.setattr(module,'_project_object',write)
    with pytest.raises((RuntimeError,ValueError,PermissionError)),conn.transaction():
        module.project_saved_batch(conn,SCOPE,'run',journal=projection_case[1],store=projection_case[2])
        if case=='rollback':raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) FROM obj_instance').fetchone()=={'count':0}
    assert conn.execute('SELECT count(*) FROM projection_outbox WHERE projected').fetchone()=={'count':0}


def test_changed_payload_is_rejected_even_when_claimed_digest_is_unchanged(projection_case):
    conn,*_=projection_case
    conn.execute("UPDATE projection_outbox SET payload=jsonb_set(payload,'{record,properties,name}','\"changed\"')")
    with pytest.raises(RuntimeError,match='PAYLOAD_HASH_MISMATCH'):execute(projection_case)
    assert conn.execute('SELECT count(*) FROM obj_instance').fetchone()=={'count':0}


def test_exact_projector_shares_existing_tenant_order_lock(projection_case,database):
    import psycopg
    from psycopg import sql
    from aos_api.ecom_projector import projection_order_lock_key
    conn,journal,store,*_=projection_case
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(%s)',(projection_order_lock_key(SCOPE),))
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as db:
            db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(database[2])))
            with pytest.raises(RuntimeError,match='PROJECTION_BUSY'),db.transaction():
                module.project_saved_batch(db,SCOPE,'run',journal=journal,store=store)
    assert conn.execute('SELECT count(*) FROM obj_instance').fetchone()=={'count':0}
    assert execute(projection_case)['projected']==1
