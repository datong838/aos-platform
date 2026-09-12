from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, pytestmark
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def owner_case(registered_db,monkeypatch):
    case=registered_db;db=case.db.owner
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
        configuration_authorize=object.__new__(CurrentFourSourceConfigurationAuthorization))
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
        result=service.read_receipt(scope=scope,idempotency_key=request.idempotencyKey,actor='actor')
        assert result['receiptId']==first['receiptId'] and result['historical'] is True and result['executable'] is False
    else:
        with pytest.raises(PermissionError):service.read_receipt(scope=scope,idempotency_key=request.idempotencyKey,actor='actor')
    assert seen==['actor']
    assert case.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1
