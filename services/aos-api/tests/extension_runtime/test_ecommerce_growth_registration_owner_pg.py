from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, pytestmark
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def owner_case(registered_db,monkeypatch):
    case=registered_db;db=case.db.owner
    db.execute("ALTER TABLE extension_runtime_binding ENABLE ROW LEVEL SECURITY")
    db.execute("ALTER TABLE extension_runtime_binding FORCE ROW LEVEL SECURITY")
    db.execute("""CREATE POLICY tenant_scope_origin_runtime ON extension_runtime_binding
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")
    db.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(case.login)))
    for table in ('extension_runtime_operation','extension_runtime_outbox','extension_runtime_event','bundle_composition'):
        db.execute(sql.SQL('CREATE TABLE {}(org_id text,project_id text)').format(sql.Identifier(table)))
        db.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        db.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
    db.execute("CREATE POLICY tenant_scope_bundle_composition_ti6 ON bundle_composition USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    db.execute('''CREATE TABLE registration_tx_probe(pid integer,tx bigint,role text);
        CREATE FUNCTION registration_probe() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN INSERT INTO registration_tx_probe VALUES(pg_backend_pid(),txid_current(),current_setting('role'));RETURN NEW;END $$;
        CREATE TRIGGER registration_probe AFTER INSERT ON extension_dispatch_registration_receipt FOR EACH ROW EXECUTE FUNCTION registration_probe();''')
    calls=[]
    @contextmanager
    def connect():
        with psycopg.connect(**{**case.db.pg,'user':case.login},autocommit=True,row_factory=dict_row) as conn:
            yield conn
    service=FirstDispatchRegistrationService(connect=connect,
        installation_store=object.__new__(PostgresInstallationStore),
        configuration_authorize=object.__new__(CurrentFourSourceConfigurationAuthorization),
        release_policy=ReleasePolicy(trust_roots=None))
    qualification_calls=[]
    monkeypatch.setattr(service._store,'load_active_baseline_in_transaction',
        lambda *a,**kw:SimpleNamespace(lock=SimpleNamespace(lock_hash=case.request['installationRef']['lockHash'])))
    def qualify(conn,**kwargs):
        qualification_calls.append(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx,current_user AS role').fetchone())
        return dict(schemaVersion='aos.ecommerce.registration-release-qualification/v1',
            lockHash=kwargs['lock'].lock_hash,packageId='solution.ecommerce.growth',operationCount=9,executable=False)
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.qualify_registration_release',qualify)
    case.qualification_calls=qualification_calls
    def check(conn,**kwargs):
        calls.append(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx,current_user AS role').fetchone())
        return dict(currentConfigurationValidated=True,requestHash=kwargs['request'].request_hash())
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.validate_current_registration_target',check)
    return case,service,calls


def test_real_transaction_registration_and_replay(owner_case):
    case,service,calls=owner_case;scope=TenantScope('org-a','project-a')
    request=FirstDispatchRegistrationRequest.model_validate(case.request)
    first=service.register(scope=scope,request=request,actor='actor')
    second=service.register(scope=scope,request=request,actor='actor')
    assert first['receiptId']==second['receiptId'] and second['replayed'] is True
    assert len(calls)==2 and all(v['role']=='aos_runtime' for v in calls)
    assert case.qualification_calls==calls
    observed=case.db.owner.execute('SELECT * FROM registration_tx_probe').fetchone()
    assert (observed['pid'],observed['tx'])==(calls[0]['pid'],calls[0]['tx'])
    assert observed['role']=='aos_extension_maintainer'
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==9


def test_preflight_denial_has_no_writes(owner_case,monkeypatch):
    case,service,_=owner_case
    def reject(*args,**kwargs):raise PermissionError('current authority denied')
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.validate_current_registration_target',reject)
    with pytest.raises(PermissionError):service.register(scope=TenantScope('org-a','project-a'),
        request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0


def test_failed_readback_rolls_back_registration(owner_case,monkeypatch):
    case,service,_=owner_case
    def reject(*args,**kwargs):raise ValueError('corrupt readback')
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.decode_registration_receipt',reject)
    with pytest.raises(ValueError):service.register(scope=TenantScope('org-a','project-a'),
        request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==0


@pytest.mark.parametrize('answer',[None,False,{},dict(currentConfigurationValidated=False)])
def test_non_authoritative_preflight_result_cannot_write(owner_case,monkeypatch,answer):
    case,service,_=owner_case
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.validate_current_registration_target',lambda *a,**kw:answer)
    with pytest.raises(PermissionError):service.register(scope=TenantScope('org-a','project-a'),
        request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0


@pytest.mark.parametrize('allowed',[True,False])
def test_history_requires_current_permission_after_runtime_drift(owner_case,monkeypatch,allowed):
    case,service,_=owner_case;scope=TenantScope('org-a','project-a')
    request=FirstDispatchRegistrationRequest.model_validate(case.request)
    first=service.register(scope=scope,request=request,actor='actor')
    case.db.owner.execute('UPDATE extension_runtime_binding SET execution_epoch=4,revision=5')
    case.db.owner.execute('GRANT SELECT,UPDATE ON bundle_installation TO aos_runtime')
    seen=[]
    monkeypatch.setattr(service._store,'lock_for_transition_in_transaction',lambda *a,**kw:SimpleNamespace(org_id=scope.org_id,project_id=scope.project_id))
    def check(**kwargs):seen.append(kwargs['actor']);return allowed
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.CurrentControlPermission',lambda **kw:check)
    if allowed:
        result=service.read_receipt(scope=scope,installation_id=request.installationRef.installation_id,idempotency_key=request.idempotencyKey,actor='actor')
        assert result['receiptId']==first['receiptId'] and result['historical'] is True and result['executable'] is False
    else:
        with pytest.raises(PermissionError):service.read_receipt(scope=scope,installation_id=request.installationRef.installation_id,idempotency_key=request.idempotencyKey,actor='actor')
    assert seen==['actor']
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


@pytest.mark.parametrize('answer',[None,False,{},dict(operationCount=9,executable=False),
    dict(schemaVersion='aos.ecommerce.registration-release-qualification/v1',lockHash='sha256:'+'f'*64,
         packageId='solution.ecommerce.growth',operationCount=9,executable=False)])
def test_qualification_failure_has_no_writes(owner_case,monkeypatch,answer):
    case,service,_=owner_case
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.qualify_registration_release',lambda *a,**kw:answer)
    with pytest.raises(PermissionError):
        service.register(scope=TenantScope('org-a','project-a'),
            request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==0


def test_revoked_signature_has_no_writes(owner_case,monkeypatch):
    case,service,_=owner_case
    def reject(*a,**kw):raise PermissionError('release revoked')
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.qualify_registration_release',reject)
    with pytest.raises(PermissionError,match='release revoked'):
        service.register(scope=TenantScope('org-a','project-a'),
            request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==0


def test_history_cannot_read_another_installation(owner_case):
    case,service,_=owner_case;scope=TenantScope('org-a','project-a')
    request=FirstDispatchRegistrationRequest.model_validate(case.request)
    service.register(scope=scope,request=request,actor='actor')
    with pytest.raises(LookupError):
        service.read_receipt(scope=scope,installation_id='99999999-9999-4999-8999-999999999999',
            idempotency_key=request.idempotencyKey,actor='actor')


def test_external_transaction_current_gate_is_read_only_and_stays_owned_by_caller(owner_case):
    case,service,calls=owner_case;scope=TenantScope('org-a','project-a')
    request=FirstDispatchRegistrationRequest.model_validate(case.request)
    with service._transaction(scope) as conn:
        before=conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx').fetchone()
        result=service.validate_current_authority_in_transaction(conn,scope=scope,request=request,actor='actor')
        after=conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx').fetchone()
        assert before==after
        assert result['requestHash']==request.request_hash() and result['executable'] is False
        assert conn.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==0
    assert case.qualification_calls==calls and len(calls)==1
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n']==0


@pytest.mark.parametrize('mode',['isolation','role','scope'])
def test_external_transaction_current_gate_rejects_untrusted_context(owner_case,mode):
    case,service,calls=owner_case;scope=TenantScope('org-a','project-a')
    with psycopg.connect(**{**case.db.pg,'user':case.login},row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.READ_COMMITTED if mode=='isolation' else psycopg.IsolationLevel.SERIALIZABLE
        conn.execute('SET LOCAL ROLE '+('aos_extension_maintainer' if mode=='role' else 'aos_runtime'))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
            ('other' if mode=='scope' else scope.org_id,scope.project_id))
        with pytest.raises((PermissionError,RuntimeError)):
            service.validate_current_authority_in_transaction(conn,scope=scope,
                request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    assert not calls


def origin_args(case, first):
    from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef
    return dict(receipt_ref=RegistrationReceiptRef(resourceType='FirstDispatchRegistrationReceipt',
        resourceId=first['receiptId'],revision=1,contentHash=first['contentHash']),
        dispatch_snapshot=first['dispatchSnapshot'],installation_id=first['installationId'],
        generation=first['generation'],execution_epoch=case.request['executionEpoch'],
        binding_revision=case.request['bindingRevision'])


def test_stored_origin_and_current_authority_share_caller_transaction(owner_case):
    case,service,calls=owner_case;scope=TenantScope('org-a','project-a')
    first=service.register(scope=scope,request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    with service._transaction(scope) as conn:
        before=conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx').fetchone()
        result=service.validate_registration_origin_in_transaction(conn,scope=scope,actor='actor',**origin_args(case,first))
        assert result['receiptRef']['resourceId']==first['receiptId'] and result['executable'] is False
        assert result['requestHash']==first['requestHash']
        assert conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx').fetchone()==before
    assert calls[-1]==case.qualification_calls[-1]
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


@pytest.mark.parametrize('drift',['id','hash','target','scope','current'])
def test_stored_origin_drift_or_current_denial_cannot_validate(owner_case,monkeypatch,drift):
    from uuid import uuid4
    from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef
    case,service,calls=owner_case;scope=TenantScope('org-a','project-a')
    first=service.register(scope=scope,request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    args=origin_args(case,first)
    if drift in ('id','hash'):
        ref=args['receipt_ref'].model_dump()
        ref['resourceId' if drift=='id' else 'contentHash']=str(uuid4()) if drift=='id' else 'sha256:'+'0'*64
        args['receipt_ref']=RegistrationReceiptRef.model_validate(ref)
    elif drift=='target':args['generation']=str(uuid4())
    elif drift=='scope':scope=TenantScope('other','project-a')
    else:
        def reject(*a,**kw):raise PermissionError('current configuration denied')
        monkeypatch.setattr('aos_api.ecommerce_growth_registration.validate_current_registration_target',reject)
    with service._transaction(scope) as conn:
        with pytest.raises((LookupError,ValueError,PermissionError)):
            service.validate_registration_origin_in_transaction(conn,scope=scope,actor='actor',**args)
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


def test_cutover_assets_entry_keeps_signature_check_while_not_claiming_runtime_readiness(owner_case,monkeypatch):
    case,service,calls=owner_case;scope=TenantScope('org-a','project-a')
    first=service.register(scope=scope,request=FirstDispatchRegistrationRequest.model_validate(case.request),actor='actor')
    seen=[]
    def assets(conn,**kw):
        seen.append(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx,current_user AS role').fetchone())
        return dict(currentConfigurationValidated=True,requestHash=kw['request'].request_hash(),runtimeStateValidated=False)
    monkeypatch.setattr('aos_api.ecommerce_growth_registration.validate_current_registration_assets',assets)
    case.db.owner.execute('UPDATE extension_runtime_binding SET revision=5,enabled=false,operation_fence=true')
    with service._transaction(scope) as conn:
        result=service.validate_cutover_registration_assets_in_transaction(conn,scope=scope,actor='actor',**origin_args(case,first))
        assert result['runtimeStateValidated'] is False and result['currentReleaseValidated'] is True
        assert result['executable'] is False
    assert len(seen)==1 and seen[0]==case.qualification_calls[-1]
