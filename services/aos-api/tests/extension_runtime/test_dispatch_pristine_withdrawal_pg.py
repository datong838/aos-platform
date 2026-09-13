from copy import deepcopy
from types import SimpleNamespace
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, pytestmark, ROOT, run as register, connection
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest


@pytest.fixture
def withdrawal_case(registered_db):
    case=registered_db;first=register(case)
    case.db.owner.execute('''CREATE TABLE extension_dispatch_cutover_operation(org_id text,project_id text,cutover_group_id uuid);
      CREATE TABLE automation_schedule_binding(org_id text,project_id text,operation_id text);
      CREATE TABLE ecommerce_growth_runtime_command_receipt(org_id text,project_id text,operation_id text);''')
    for filename in ('a0v_029_dispatch_withdrawal_receipt.py','a0v_030_dispatch_pristine_withdrawal.py'):
        path=ROOT/'alembic/versions'/filename
        spec=importlib.util.spec_from_file_location(filename,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.op=SimpleNamespace(execute=case.db.owner.execute);m.upgrade()
    case.withdraw=RegistrationWithdrawalRequest(registrationReceiptRef=dict(resourceType='FirstDispatchRegistrationReceipt',
        resourceId=first['receiptId'],revision=1,contentHash=first['contentHash']),expectedInstallationEtag=5,idempotencyKey='withdraw-1').model_dump(mode='json')
    return case


def withdraw(case,request=None,actor='actor',scope=('org-a','project-a')):
    with connection(case,scope=scope) as c:
        return c.execute('SELECT extension_dispatch_withdraw_a0v_030(%s,%s)',(Jsonb(request or case.withdraw),actor)).fetchone()[0]


def counts(case):
    return tuple(case.db.owner.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in
        ('extension_operation_dispatch_binding','extension_dispatch_registration_receipt','extension_dispatch_withdrawal_receipt'))


def test_atomic_release_keeps_history_and_replays(withdrawal_case):
    c=withdrawal_case;first=withdraw(c);second=withdraw(c)
    assert counts(c)==(0,1,1)
    assert first['receiptId']==second['receiptId'] and second['replayed'] is True
    assert first['releasedOperationCount']==9 and first['executable'] is False
    request=deepcopy(c.withdraw);request['idempotencyKey']='different'
    with pytest.raises(psycopg.Error):withdraw(c,request)
    assert counts(c)==(0,1,1)


@pytest.mark.parametrize('change',['actor','tenant','etag','ref','partial','revision','unfenced','cutover','schedule','command','marking','extra','bool_etag'])
def test_invalid_or_used_target_leaves_no_partial_write(withdrawal_case,change):
    c=withdrawal_case;request=deepcopy(c.withdraw);kwargs={}
    if change=='actor':kwargs['actor']='other'
    elif change=='tenant':kwargs['scope']=('other','project-a')
    elif change=='etag':request['expectedInstallationEtag']=6
    elif change=='bool_etag':request['expectedInstallationEtag']=True
    elif change=='ref':request['registrationReceiptRef']['contentHash']='sha256:'+'0'*64
    elif change=='partial':c.db.owner.execute("DELETE FROM extension_operation_dispatch_binding WHERE operation_id='ecommerce_growth_case_put'")
    elif change=='revision':c.db.owner.execute('UPDATE extension_operation_dispatch_binding SET revision=2')
    elif change=='unfenced':c.db.owner.execute('UPDATE extension_operation_dispatch_binding SET operation_fence=false')
    elif change=='cutover':c.db.owner.execute("INSERT INTO extension_dispatch_cutover_operation VALUES('org-a','project-a',%s)",(c.request['groupId'],))
    elif change in ('schedule','command'):
        table='automation_schedule_binding' if change=='schedule' else 'ecommerce_growth_runtime_command_receipt'
        c.db.owner.execute("INSERT INTO "+table+" VALUES('org-a','project-a','ecommerce_growth_case_put')")
    elif change=='marking':c.db.owner.execute('UPDATE bundle_composition_lock SET permission_diff_json=%s',(Jsonb(dict(target=dict(markings=['secret']))),))
    else:request['force']=True
    before=counts(c)
    with pytest.raises(psycopg.Error):withdraw(c,request,**kwargs)
    assert counts(c)==before


def test_caller_rollback_restores_both_occupancy_and_receipt(withdrawal_case):
    c=withdrawal_case
    with pytest.raises(RuntimeError):
        with connection(c) as conn:
            conn.execute('SELECT extension_dispatch_withdraw_a0v_030(%s,%s)',(Jsonb(c.withdraw),'actor'))
            raise RuntimeError('simulated caller interruption')
    assert counts(c)==(9,1,0)


def test_concurrent_same_intent_is_single_release(withdrawal_case):
    c=withdrawal_case;barrier=Barrier(2)
    def attempt():
        barrier.wait()
        try:return withdraw(c)['receiptId']
        except psycopg.errors.SerializationFailure:return 'serialization-abort'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    ids=[r for r in results if r!='serialization-abort']
    assert len(ids)>=1 and len(set(ids))==1 and counts(c)==(0,1,1)


def test_runtime_cannot_execute_write_entry(withdrawal_case):
    with psycopg.connect(**withdrawal_case.db.pg,autocommit=True) as c:
        c.execute('SET ROLE aos_runtime')
        assert c.execute("SELECT has_function_privilege(current_user,'extension_dispatch_withdraw_a0v_030(jsonb,text)','EXECUTE')").fetchone()[0] is False


def test_new_registration_after_withdrawal_and_old_replay_cannot_remove_it(withdrawal_case):
    c=withdrawal_case;old=withdraw(c)
    replacement=deepcopy(c.request);replacement['groupId']=str(uuid4());replacement['idempotencyKey']='replacement-first'
    new=register(c,replacement)
    assert counts(c)==(9,2,1) and new['groupId']!=old['groupId']
    assert withdraw(c)['receiptId']==old['receiptId']
    assert counts(c)==(9,2,1)
    assert register(c)['groupId']==old['groupId']
    assert counts(c)==(9,2,1)


def test_replay_still_checks_current_actor_permission(withdrawal_case):
    c=withdrawal_case;withdraw(c)
    c.db.owner.execute("DELETE FROM meta_membership WHERE subject='actor'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):withdraw(c)
    assert counts(c)==(0,1,1)


def test_fractional_ref_revision_is_not_a_strict_integer(withdrawal_case):
    c=withdrawal_case;request=deepcopy(c.withdraw);request['registrationReceiptRef']['revision']=1.0
    with pytest.raises(psycopg.Error):withdraw(c,request)
    assert counts(c)==(9,1,0)


def test_privileged_session_cannot_use_entry_even_after_role_adoption(withdrawal_case):
    c=withdrawal_case
    with psycopg.connect(**c.db.pg) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        conn.execute('SET LOCAL ROLE aos_extension_maintainer')
        conn.execute("SELECT set_config('aos.org_id','org-a',true),set_config('aos.project_id','project-a',true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT extension_dispatch_withdraw_a0v_030(%s,%s)',(Jsonb(c.withdraw),'actor'))
    assert counts(c)==(9,1,0)


def test_nonserializable_session_is_rejected(withdrawal_case):
    c=withdrawal_case
    with psycopg.connect(**{**c.db.pg,'user':c.login}) as conn:
        conn.execute('SET LOCAL ROLE aos_extension_maintainer')
        conn.execute("SELECT set_config('aos.org_id','org-a',true),set_config('aos.project_id','project-a',true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT extension_dispatch_withdraw_a0v_030(%s,%s)',(Jsonb(c.withdraw),'actor'))
    assert counts(c)==(9,1,0)


@pytest.fixture
def withdrawal_owner(withdrawal_case,monkeypatch):
    from contextlib import contextmanager
    from psycopg import sql
    from psycopg.rows import dict_row
    from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
    c=withdrawal_case;db=c.db.owner
    db.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(c.login)))
    db.execute('ALTER TABLE extension_runtime_binding ENABLE ROW LEVEL SECURITY; ALTER TABLE extension_runtime_binding FORCE ROW LEVEL SECURITY')
    db.execute("CREATE POLICY tenant_scope_binding_owner ON extension_runtime_binding USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    for table in ('extension_runtime_operation','extension_runtime_outbox','extension_runtime_event','bundle_composition'):
        db.execute(sql.SQL('CREATE TABLE {}(org_id text,project_id text)').format(sql.Identifier(table)))
        db.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        db.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
    db.execute("CREATE POLICY tenant_scope_bundle_composition_ti6 ON bundle_composition USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    @contextmanager
    def connect():
        with psycopg.connect(**{**c.db.pg,'user':c.login},autocommit=True,row_factory=dict_row) as conn:yield conn
    service=FirstDispatchRegistrationService(connect=connect,installation_store=object.__new__(PostgresInstallationStore),
        configuration_authorize=object.__new__(CurrentFourSourceConfigurationAuthorization),release_policy=ReleasePolicy(trust_roots=None))
    # SQL entry checks actual membership/markings/CAS. Owner permission composition
    # below is an explicit fixture because this DB has only minimal installation columns.
    db.execute('''CREATE TABLE withdrawal_tx_probe(pid integer,tx bigint,role text);
        CREATE FUNCTION withdrawal_probe() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN INSERT INTO withdrawal_tx_probe VALUES(pg_backend_pid(),txid_current(),current_setting('role'));RETURN NEW;END $$;
        CREATE TRIGGER withdrawal_probe AFTER INSERT ON extension_dispatch_withdrawal_receipt FOR EACH ROW EXECUTE FUNCTION withdrawal_probe();''')
    checks=[]
    def permission(self,conn,scope,installation_id,actor):
        checks.append(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx,current_user AS role').fetchone())
    monkeypatch.setattr(FirstDispatchRegistrationService,'_authorize_receipt_access',permission)
    return c,service,checks


def test_owner_withdraws_and_reads_same_receipt(withdrawal_owner):
    from aos_api.tenant_scope import TenantScope
    c,service,checks=withdrawal_owner;scope=TenantScope('org-a','project-a')
    first=service.withdraw(installation_id=c.request['installationRef']['installationId'],scope=scope,request=RegistrationWithdrawalRequest.model_validate(c.withdraw),actor='actor')
    second=service.read_withdrawal_receipt(scope=scope,installation_id=c.request['installationRef']['installationId'],idempotency_key='withdraw-1',actor='actor')
    assert first['receiptId']==second['receiptId'] and second['historical'] is True
    assert counts(c)==(0,1,1) and all(check['role']=='aos_runtime' for check in checks)
    probe=c.db.owner.execute('SELECT * FROM withdrawal_tx_probe').fetchone()
    assert (probe['pid'],probe['tx'])==(checks[0]['pid'],checks[0]['tx'])
    assert probe['role']=='aos_extension_maintainer'


def test_owner_corrupt_readback_rolls_back_everything(withdrawal_owner,monkeypatch):
    from aos_api.tenant_scope import TenantScope
    c,service,_=withdrawal_owner
    def corrupt(*a,**kw):raise ValueError('corrupt readback')
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.decode_withdrawal_receipt',corrupt)
    with pytest.raises(ValueError):service.withdraw(installation_id=c.request['installationRef']['installationId'],scope=TenantScope('org-a','project-a'),request=RegistrationWithdrawalRequest.model_validate(c.withdraw),actor='actor')
    assert counts(c)==(9,1,0)


def test_owner_permission_denial_prevents_sql_mutation(withdrawal_owner,monkeypatch):
    from aos_api.tenant_scope import TenantScope
    c,service,_=withdrawal_owner
    def denied(*a,**kw):raise PermissionError('current authority denied')
    monkeypatch.setattr(service,'_authorize_receipt_access',denied)
    with pytest.raises(PermissionError):service.withdraw(installation_id=c.request['installationRef']['installationId'],scope=TenantScope('org-a','project-a'),request=RegistrationWithdrawalRequest.model_validate(c.withdraw),actor='actor')
    assert counts(c)==(9,1,0)


def test_owner_installation_path_cannot_select_another_origin(withdrawal_owner):
    from aos_api.tenant_scope import TenantScope
    c,service,checks=withdrawal_owner
    with pytest.raises(ValueError,match='path differs'):
        service.withdraw(installation_id=str(uuid4()),scope=TenantScope('org-a','project-a'),request=RegistrationWithdrawalRequest.model_validate(c.withdraw),actor='actor')
    assert counts(c)==(9,1,0) and checks==[]


def test_http_to_real_owner_and_atomic_receipt(withdrawal_owner):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from aos_api.auth import Principal,require_principal
    from aos_api.errors import register_exception_handlers
    from aos_api.routers.bundle_runtime_installations import router
    c,service,_=withdrawal_owner
    app=FastAPI();register_exception_handlers(app);app.include_router(router)
    app.state.extension_runtime_control_plane=SimpleNamespace(first_dispatch_registration_service=service)
    app.dependency_overrides[require_principal]=lambda:Principal(subject='actor',org_id='org-a',project_id='project-a',roles=['admin'],markings=[])
    path='/v1/bundle-runtime-installations/'+c.request['installationRef']['installationId']+'/ecommerce-growth-registrations/withdrawals'
    with TestClient(app) as client:
        response=client.post(path,json=c.withdraw,headers={'Idempotency-Key':'withdraw-1','If-Match':'"5"'})
        assert response.status_code==201,response.text
        history=client.get(path+'/receipt',headers={'Idempotency-Key':'withdraw-1'})
        assert history.status_code==200,history.text
        assert history.json()['receiptId']==response.json()['receiptId']
        assert history.json()['historical'] is True
    assert counts(c)==(0,1,1)
