from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
from types import SimpleNamespace
from uuid import uuid4
from threading import Barrier

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from test_dispatch_registration_receipt_pg import receipt_db, database, pytestmark, ROOT
from test_ecommerce_growth_registration_contracts import payload
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.asset_registry.canonical_json import canonical_sha256


@pytest.fixture
def registered_db(receipt_db):
    db,installation,generation=receipt_db;owner=db.owner
    request=payload();request['installationRef']['installationId']=str(installation)
    request['generation']=str(generation)
    owner.execute('''ALTER TABLE extension_runtime_binding ADD COLUMN revision bigint,
        ADD COLUMN execution_epoch bigint, ADD COLUMN installation_revision bigint,
        ADD COLUMN enabled boolean, ADD COLUMN operation_fence boolean,
        ADD COLUMN desired_state text, ADD COLUMN observed_state text, ADD COLUMN config_ref jsonb;
        CREATE TABLE bundle_installation(org_id text,project_id text,installation_id uuid,
          installation_pk uuid,current_revision bigint,active_revision bigint,etag_version bigint);
        CREATE TABLE bundle_installation_revision(org_id text,project_id text,installation_pk uuid,
          revision bigint,state text,lock_hash text,overlay_revision text,composition_pk uuid,lock_revision bigint);
        CREATE TABLE bundle_composition_lock(org_id text,project_id text,composition_pk uuid,revision bigint,
          lock_payload jsonb,permission_diff_json jsonb);
        CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text);
        CREATE TABLE authz_tuple(org_id text,project_id text,user_key text,relation text,object_key text);
        CREATE TABLE extension_runtime_configuration(org_id text,project_id text,installation_id uuid,
          generation uuid,configuration_id uuid,revision bigint,content_hash text);''')
    owner.execute("UPDATE extension_runtime_binding SET revision=4,execution_epoch=3,installation_revision=5,enabled=true,operation_fence=false,desired_state='enabled',observed_state='ready',config_ref=%s",(Jsonb(request['configRef']),))
    owner.execute("INSERT INTO bundle_installation VALUES('org-a','project-a',%s,%s,5,5,5)",(installation,installation))
    owner.execute("INSERT INTO bundle_installation_revision VALUES('org-a','project-a',%s,5,'active',%s,'overlay-1',%s,1)",(installation,request['installationRef']['lockHash'],installation))
    owner.execute("INSERT INTO bundle_composition_lock VALUES('org-a','project-a',%s,1,%s,%s)",(installation,Jsonb(dict(resolved=[dict(id='solution.ecommerce.growth')])),Jsonb(dict(target=dict(markings=[])))))
    owner.execute("INSERT INTO meta_membership VALUES('org-a','project-a','actor','admin')")
    owner.execute("INSERT INTO extension_runtime_configuration VALUES('org-a','project-a',%s,%s,%s,1,%s)",(installation,generation,request['configRef']['configurationId'],request['configRef']['hash']))
    for filename in ('ar2_001_ecommerce_dispatch_authority.py','a0v_027_dispatch_first_registration.py'):
        path=ROOT/'alembic/versions'/filename
        spec=importlib.util.spec_from_file_location(filename,path);module=importlib.util.module_from_spec(spec)
        if filename.startswith('a0v_027'):
            created=owner.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_extension_maintainer'").fetchone() is None
            if created:owner.execute('CREATE ROLE aos_extension_maintainer NOLOGIN NOSUPERUSER NOBYPASSRLS')
        spec.loader.exec_module(module);module.op=SimpleNamespace(execute=owner.execute);module.upgrade()
    login='reg_'+uuid4().hex[:16]
    owner.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT').format(sql.Identifier(login)))
    owner.execute(sql.SQL('GRANT aos_extension_maintainer TO {}').format(sql.Identifier(login)))
    try:yield SimpleNamespace(db=db,request=request,login=login)
    finally:
        owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))
        if created:
            owner.execute('REVOKE ALL ON FUNCTION extension_dispatch_register_a0v_027(jsonb,text) FROM aos_extension_maintainer')
            owner.execute('DROP ROLE aos_extension_maintainer')


@contextmanager
def connection(case,*,scope=('org-a','project-a')):
    with psycopg.connect(**{**case.db.pg,'user':case.login}) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        conn.execute('SET LOCAL ROLE aos_extension_maintainer')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope)
        yield conn


def run(case,request=None,actor='actor',scope=('org-a','project-a')):
    with connection(case,scope=scope) as conn:
        return conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s)',(Jsonb(request or case.request),actor)).fetchone()[0]


def test_nine_fenced_and_idempotent_receipt(registered_db):
    case=registered_db;first=run(case);again=run(case)
    assert first['receiptId']==again['receiptId'] and again['replayed'] is True
    assert first['requestHash']==canonical_sha256(case.request)
    body={k:v for k,v in first.items() if k not in ('contentHash','replayed')}
    assert first['contentHash']==canonical_sha256(body)
    rows=case.db.owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall()
    assert [r['operation_id'] for r in rows]==sorted(ECOMMERCE_GROWTH_OPERATIONS)
    assert all(r['operation_fence'] is True and r['handler_kind']=='legacy' and r['generation'] is None for r in rows)
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


@pytest.mark.parametrize('case_name',['tenant','actor','revision','configuration','partial','extra','marking'])
def test_rejects_invalid_registration_without_partial_writes(registered_db,case_name):
    case=registered_db;request=deepcopy(case.request);scope=('org-a','project-a');actor='actor'
    if case_name=='tenant':scope=('other','project-a')
    elif case_name=='actor':actor='unknown'
    elif case_name=='revision':request['bindingRevision']+=1
    elif case_name=='configuration':request['configRef']['revision']+=1
    elif case_name=='extra':request['operationIds']=[]
    elif case_name=='marking':case.db.owner.execute('UPDATE bundle_composition_lock SET permission_diff_json=%s',
        (Jsonb(dict(target=dict(markings=['restricted']))),))
    else:
        case.db.owner.execute("INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,handler_kind,operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by) VALUES('org-a','project-a',%s,'legacy',true,1,%s,1,'actor')",(ECOMMERCE_GROWTH_OPERATIONS[0],uuid4()))
    with pytest.raises(psycopg.Error):run(case,request,actor,scope)
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==0
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==(1 if case_name=='partial' else 0)


def test_runtime_has_no_function_access(registered_db):
    case=registered_db
    with psycopg.connect(**case.db.pg,autocommit=True) as conn:
        conn.execute('SET ROLE aos_runtime')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s)',(Jsonb(case.request),'actor'))


def test_same_key_different_request_and_actor_rejected(registered_db):
    case=registered_db;run(case)
    request=deepcopy(case.request);request['groupId']=str(uuid4())
    with pytest.raises(psycopg.Error):run(case,request)
    case.db.owner.execute("INSERT INTO meta_membership VALUES('org-a','project-a','other-actor','admin')")
    with pytest.raises(psycopg.Error):run(case,actor='other-actor')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


def test_crash_before_commit_rolls_back_both(registered_db):
    case=registered_db
    with pytest.raises(RuntimeError):
        with connection(case) as conn:
            conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s)',(Jsonb(case.request),'actor'))
            raise RuntimeError('simulated process failure before commit')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==0


def test_two_groups_cannot_register_the_same_operations(registered_db):
    case=registered_db;barrier=Barrier(2)
    def attempt(index):
        request=deepcopy(case.request);request['groupId']=str(uuid4());request['idempotencyKey']='concurrent-'+str(index)
        try:
            with connection(case) as conn:
                barrier.wait(timeout=5)
                conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s)',(Jsonb(request),'actor'))
            return True
        except psycopg.Error:return False
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
    assert sorted(results)==[False,True]
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==9
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


@pytest.mark.parametrize('key,value',[('idempotencyKey',123),('bindingRevision',True),('executionEpoch','3')])
def test_sql_request_does_not_coerce_types(registered_db,key,value):
    case=registered_db;request=deepcopy(case.request);request[key]=value
    with pytest.raises(psycopg.Error):run(case,request)


def test_privileged_session_and_wrong_isolation_rejected(registered_db):
    case=registered_db
    for user,isolation in [('postgres','SERIALIZABLE'),(case.login,'READ COMMITTED')]:
        with psycopg.connect(**{**case.db.pg,'user':user}) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL '+isolation)
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            conn.execute("SELECT set_config('aos.org_id','org-a',true),set_config('aos.project_id','project-a',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s)',(Jsonb(case.request),'actor'))
