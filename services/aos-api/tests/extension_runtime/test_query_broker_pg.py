"""Signed query broker on the dedicated disposable PostgreSQL only."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
import time
import uuid

import psycopg
from psycopg import sql
import pytest

from test_lifecycle_pg import database,seed,pytestmark
from test_admission import fixture as signed_release


@pytest.fixture
def broker_case(database):
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.extension_runtime.runtime_gate import CurrentPolicy
    admin,_,schema=database
    installation,_=seed(admin)
    generation=uuid.uuid4()
    release,files=signed_release(namespace=schema,now=datetime.now(timezone.utc))
    selected=release['selected']
    current=CurrentInstallationRef(installationId=str(installation),revision=1,
        lockHash='sha256:'+'a'*64,overlayRevision='test-overlay')
    admin.execute("""INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,profile_ref,
         config_ref,desired_state,observed_state,enabled,operation_fence)
        VALUES('org-org','dev-project',%s,%s,1,%s::jsonb,'internal-python-v1','{}','enabled','ready',true,false)""",
        (installation,generation,'{"lockHash":"'+current.lock_hash+'"}'))
    admin.execute('CREATE TABLE products(org_id text,project_id text,id bigint,name text)')
    admin.execute("INSERT INTO products VALUES('org-org','dev-project',1,'栖月汇商品'),('dev-org','dev-project',2,'隔离记录')")
    admin.execute('ALTER TABLE products ENABLE ROW LEVEL SECURITY')
    admin.execute('ALTER TABLE products FORCE ROW LEVEL SECURITY')
    admin.execute("CREATE POLICY tenant_products ON products USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    role='ar1c_'+uuid.uuid4().hex
    admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role)))
    admin.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(role)))
    admin.execute(sql.SQL('GRANT SELECT ON {} TO {}').format(sql.Identifier(schema,'products'),sql.Identifier(role)))
    admin.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    class Store:
        def __init__(self):
            self.selected=selected

        def load_active_baseline_in_transaction(self,conn,**kwargs):
            conn.execute('SELECT installation_id FROM bundle_installation WHERE installation_id=%s FOR SHARE',(installation,))
            return SimpleNamespace(server_ref=current,lock=SimpleNamespace(lock_hash=current.lock_hash,
                payload=SimpleNamespace(resolved=[self.selected])))
    @contextmanager
    def query_connect():
        with psycopg.connect(host='127.0.0.1',port=18432,user=role,dbname='postgres',autocommit=True) as conn:
            yield conn
    policy=CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)
    from aos_api.extension_runtime.query_broker import SignedQueryBroker
    broker=SignedQueryBroker(query_connect=query_connect,installation_store=Store(),
        load_record=lambda value:release['record'],read_artifact=lambda value,path,limit:files[path],
        release_policy=release['policy'],check_current_policy=lambda conn,baseline:policy)
    args=dict(conn=admin,org_id='org-org',project_id='dev-project',current_ref=current,
        generation=generation,request_epoch=1,selected=selected,operation_id='products.read',parameter=1)
    try:yield broker,args,admin,schema,role
    finally:
        admin.execute(sql.SQL('REVOKE ALL ON {} FROM {}').format(sql.Identifier(schema,'products'),sql.Identifier(role)))
        admin.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM {}').format(sql.Identifier(schema),sql.Identifier(role)))
        admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_query_broker_joins_signed_release_epoch_and_restricted_read(broker_case):
    broker,args,_,_,_=broker_case
    with args['conn'].transaction():
        assert broker.dispatch(**args)==(('栖月汇商品',),)


@pytest.mark.parametrize('case',['operation','epoch','fence','policy','tenant','parameter'])
def test_query_broker_rejects_before_untrusted_read(broker_case,case):
    from aos_api.extension_runtime.runtime_gate import CurrentPolicy
    broker,args,admin,_,_=broker_case
    if case=='operation':args['operation_id']='missing.read'
    elif case=='epoch':args['request_epoch']=2
    elif case=='fence':admin.execute('UPDATE extension_runtime_binding SET operation_fence=true,enabled=false,execution_epoch=2')
    elif case=='policy':broker.check_current_policy=lambda c,b:CurrentPolicy(permissions_valid=True,budget_valid=False,policy_valid=True)
    elif case=='tenant':args['org_id']='dev-org'
    else:args['parameter']='1 OR 1=1'
    with pytest.raises((ValueError,LookupError,PermissionError)):
        with admin.transaction():broker.dispatch(**args)


def test_query_broker_holds_binding_lock_until_actual_read_returns(broker_case,monkeypatch):
    import aos_api.extension_runtime.query_broker as module
    broker,args,admin,schema,_=broker_case
    original=module.read_registered_rows
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
        other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        other.execute("SET lock_timeout='100ms'")
        fence="UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,observed_state='draining',execution_epoch=execution_epoch+1,revision=revision+1"
        def observed(*a,**kw):
            with pytest.raises(psycopg.errors.LockNotAvailable):
                other.execute(fence)
            return original(*a,**kw)
        monkeypatch.setattr(module,'read_registered_rows',observed)
        with admin.transaction():assert broker.dispatch(**args)==(('栖月汇商品',),)
        other.execute(fence)


def test_query_broker_rejects_privileged_query_connection(broker_case):
    from contextlib import contextmanager
    broker,args,admin,_,_=broker_case
    @contextmanager
    def privileged():yield admin
    broker.query_connect=privileged
    with pytest.raises(PermissionError):
        with admin.transaction():broker.dispatch(**args)


def test_query_broker_rechecks_signed_evidence_after_binding_lock_wait(broker_case):
    from aos_api.asset_registry.contracts import BundleEvidenceType
    from aos_api.asset_registry.errors import ManifestInvalidError
    broker,args,_,schema,_=broker_case
    record=broker.load_record(args['selected'])
    expires_at=datetime.now(timezone.utc)+timedelta(seconds=0.8)
    record.evidence=[item.model_copy(update={'expires_at':expires_at})
        if item.type==BundleEvidenceType.CONTENT_HASH else item for item in record.evidence]
    result=broker.release_policy.evaluate(record,checked_at=datetime.now(timezone.utc))
    selected=args['selected'].model_copy(update={
        'release_evidence_revision':result.release_evidence_revision,
        'signature_fingerprint':result.signature_fingerprint,
    })
    args['selected']=selected
    broker.installation_store.selected=selected
    opened=[]
    original_connect=broker.query_connect
    @contextmanager
    def counted_connect():
        opened.append(True)
        with original_connect() as conn:
            yield conn
    broker.query_connect=counted_connect
    application_name='ar1c-expiry-'+uuid.uuid4().hex
    connect=dict(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True)
    with psycopg.connect(**connect) as blocker,psycopg.connect(**connect,application_name=application_name) as control:
        for conn in (blocker,control):
            conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
        blocker.execute('BEGIN')
        blocker.execute('SELECT installation_id FROM extension_runtime_binding FOR UPDATE')
        call_args={**args,'conn':control}
        def dispatch():
            with control.transaction():
                return broker.dispatch(**call_args)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(dispatch)
            deadline=time.monotonic()+2
            waiting=False
            while time.monotonic()<deadline:
                row=blocker.execute("SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s",(application_name,)).fetchone()
                if row and row[0]=='Lock':
                    waiting=True
                    break
                time.sleep(0.01)
            assert waiting and not future.done()
            time.sleep(max(0,(expires_at-datetime.now(timezone.utc)).total_seconds())+0.1)
            blocker.execute('COMMIT')
            with pytest.raises(ManifestInvalidError):
                future.result(timeout=5)
    assert opened==[]
