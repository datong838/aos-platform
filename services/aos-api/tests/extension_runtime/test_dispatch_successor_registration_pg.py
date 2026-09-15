from copy import deepcopy
import importlib.util
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_successor_registration import decode_successor_receipt
from aos_api.tenant_scope import TenantScope
import test_investigation_description_store_pg as storage_fixture
from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, connection, run

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='dedicated PostgreSQL opt-in required')


@pytest.fixture(autouse=True)
def pg_target(monkeypatch):
    monkeypatch.setattr(storage_fixture,'PG',dict(host='127.0.0.1',port=18434,user='aos_test',dbname='aos_test_admin'))


@pytest.fixture
def successor(registered_db):
    case=registered_db;owner=case.db.owner
    run(case)
    owner.execute('UPDATE extension_operation_dispatch_binding SET revision=5,cutover_group_revision=5')
    snapshot=owner.execute("""SELECT jsonb_agg(jsonb_build_object('operationId',operation_id,'handlerKind',handler_kind,
        'installationId',installation_id,'generation',generation,'executionEpoch',execution_epoch,
        'operationFence',operation_fence,'revision',revision,'cutoverGroupId',cutover_group_id::text,
        'cutoverGroupRevision',cutover_group_revision) ORDER BY operation_id) AS data FROM extension_operation_dispatch_binding""").fetchone()['data']
    old_install,old_generation,activation,operation,receipt=tuple(uuid4() for _ in range(5))
    owner.execute("""INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,generation,
        revision,execution_epoch,enabled,operation_fence,desired_state,observed_state)
        VALUES('org-a','project-a',%s,%s,11,6,false,true,'disabled','unknown')""",(old_install,old_generation))
    owner.execute('''CREATE TABLE extension_dispatch_lifecycle_receipt(org_id text,project_id text,receipt_id uuid,
        runtime_operation_id uuid,phase text,request_hash text,authority_data jsonb,content_hash text);
        CREATE TABLE extension_dispatch_lifecycle_operation(org_id text,project_id text,runtime_operation_id uuid,
          activation_operation_id uuid,cutover_group_id uuid,status text,request_hash text,operation_ids jsonb,fenced_group_revision bigint);
        CREATE TABLE extension_dispatch_lifecycle_event(org_id text,project_id text,runtime_operation_id uuid,
          sequence bigint,event_type text,payload jsonb,payload_hash text);
        CREATE TABLE extension_dispatch_cutover_operation(org_id text,project_id text,cutover_operation_id uuid,
          kind text,status text,cutover_group_id uuid,target_installation_id uuid,target_generation uuid);
        CREATE TABLE extension_runtime_operation(org_id text,project_id text,operation_id uuid,installation_id uuid,kind text,status text,phase text);
        CREATE TABLE extension_dispatch_claim_gate(org_id text,project_id text,cutover_group_id uuid);
        CREATE TABLE extension_runtime_execution_attempt(org_id text,project_id text,installation_id uuid,generation uuid,state text);
        CREATE TABLE automation_occurrence(org_id text,project_id text,occurrence_id uuid,installation_id uuid,generation uuid,status text);
        CREATE TABLE automation_occurrence_dispatch_attempt(org_id text,project_id text,occurrence_id uuid,status text);
        CREATE TABLE extension_runtime_resource_lease(org_id text,project_id text,operation_id uuid,generation uuid,cleanup_state text,observed_release boolean);''')
    body=dict(tenant=dict(orgId='org-a',projectId='project-a'),runtimeOperationId=str(operation),activationOperationId=str(activation),
        phase='detach',status='detached',requestHash='sha256:'+'d'*64,dispatchSnapshot=snapshot,operationIds=[r['operationId'] for r in snapshot])
    h=canonical_sha256(body)
    event=dict(runtimeOperationId=str(operation),phase='detach',receiptId=str(receipt),contentHash=h)
    owner.execute("INSERT INTO extension_dispatch_lifecycle_receipt VALUES('org-a','project-a',%s,%s,'detach',%s,%s,%s)",
                  (receipt,operation,body['requestHash'],Jsonb(body),h))
    owner.execute("INSERT INTO extension_dispatch_lifecycle_operation VALUES('org-a','project-a',%s,%s,%s,'detached',%s,%s,4)",
                  (operation,activation,case.request['groupId'],body['requestHash'],Jsonb(body['operationIds'])))
    owner.execute("INSERT INTO extension_dispatch_lifecycle_event VALUES('org-a','project-a',%s,2,'DISPATCH_DISABLED_DETACHED',%s,%s)",
                  (operation,Jsonb(event),canonical_sha256(event)))
    owner.execute("INSERT INTO extension_dispatch_cutover_operation VALUES('org-a','project-a',%s,'activate','resumed',%s,%s,%s)",
                  (activation,case.request['groupId'],old_install,old_generation))
    owner.execute("INSERT INTO extension_runtime_operation VALUES('org-a','project-a',%s,%s,'disable','succeeded','succeeded')",(operation,old_install))
    path=storage_fixture.ROOT/'alembic/versions/a0v_056_dispatch_successor_registration.py'
    spec=importlib.util.spec_from_file_location('successor_migration',path);migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration);migration.op=SimpleNamespace(execute=owner.execute);migration.upgrade()
    request=dict(schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',registration=deepcopy(case.request),
        expectedGroupRevision=5,predecessorDetachReceiptRef=dict(resourceType='DispatchDisableDetachReceipt',
            resourceId=str(receipt),revision=1,contentHash=h))
    request['registration']['idempotencyKey']='successor-first'
    case.successor=request;case.old_install=old_install;case.old_generation=old_generation
    return case


def register(case,request=None,scope=('org-a','project-a'),actor='actor'):
    with connection(case,scope=scope) as conn:
        return conn.execute('SELECT extension_dispatch_successor_register_a0v_056(%s,%s)',(Jsonb(request or case.successor),actor)).fetchone()[0]


def test_successor_adds_only_receipt_preserves_dispatch_and_replays(successor):
    owner=successor.db.owner
    before=owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall()
    result=register(successor);again=register(successor)
    assert result['receiptId']==again['receiptId'] and again['replayed']
    row=owner.execute('SELECT * FROM extension_dispatch_successor_registration_receipt').fetchone()
    assert decode_successor_receipt(dict(row),scope=TenantScope('org-a','project-a'))['executable'] is False
    assert owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall()==before


@pytest.mark.parametrize('fault',['parent','group','snapshot','actor','tenant','active','gate','attempt','unknown','resource'])
def test_successor_rejects_incomplete_or_drifted_predecessor(successor,fault):
    case=successor;owner=case.db.owner;request=deepcopy(case.successor);actor='actor';scope=('org-a','project-a')
    if fault=='parent':request['predecessorDetachReceiptRef']['contentHash']='sha256:'+'e'*64
    elif fault=='group':request['expectedGroupRevision']=4
    elif fault=='snapshot':owner.execute('UPDATE extension_operation_dispatch_binding SET revision=revision+1')
    elif fault=='actor':actor='nobody'
    elif fault=='tenant':scope=('other','project-a')
    elif fault=='active':owner.execute('UPDATE extension_runtime_binding SET enabled=true WHERE installation_id=%s',(case.old_install,))
    elif fault=='gate':owner.execute("INSERT INTO extension_dispatch_claim_gate VALUES('org-a','project-a',%s)",(request['registration']['groupId'],))
    elif fault=='attempt':owner.execute("INSERT INTO extension_runtime_execution_attempt VALUES('org-a','project-a',%s,%s,'running')",(case.old_install,case.old_generation))
    elif fault=='unknown':
        occurrence=uuid4()
        owner.execute("INSERT INTO automation_occurrence VALUES('org-a','project-a',%s,%s,%s,'accepted')",(occurrence,case.old_install,case.old_generation))
        owner.execute("INSERT INTO automation_occurrence_dispatch_attempt VALUES('org-a','project-a',%s,'unknown')",(occurrence,))
    else:owner.execute("INSERT INTO extension_runtime_resource_lease SELECT org_id,project_id,operation_id,%s,'uncertain',false FROM extension_runtime_operation",(case.old_generation,))
    with pytest.raises(Exception):register(case,request,scope,actor)
    assert owner.execute('SELECT count(*) AS n FROM extension_dispatch_successor_registration_receipt').fetchone()['n']==0


@pytest.mark.parametrize('statement',[
    'UPDATE extension_dispatch_successor_registration_receipt SET payload=payload',
    'DELETE FROM extension_dispatch_successor_registration_receipt',
    'TRUNCATE extension_dispatch_successor_registration_receipt'])
def test_successor_history_is_immutable_even_for_owner(successor,statement):
    register(successor)
    with pytest.raises(Exception):successor.db.owner.execute(statement)


def test_successor_same_key_payload_drift_is_rejected(successor):
    first=register(successor)
    changed=deepcopy(successor.successor);changed['expectedGroupRevision']+=1
    with pytest.raises(Exception,match='idempotency conflict'):register(successor,changed)
    assert register(successor)['receiptId']==first['receiptId']


def test_successor_waits_for_same_cutover_group_lock(successor):
    from psycopg.errors import LockNotAvailable
    with connection(successor) as held:
        held.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                     ('org-a'+chr(31)+'project-a'+chr(31)+successor.request['groupId'],))
        with pytest.raises(LockNotAvailable):
            with connection(successor) as writer:
                writer.execute("SET LOCAL lock_timeout='100ms'")
                writer.execute('SELECT extension_dispatch_successor_register_a0v_056(%s,%s)',(Jsonb(successor.successor),'actor'))
        assert successor.db.owner.execute('SELECT count(*) AS n FROM extension_dispatch_successor_registration_receipt').fetchone()['n']==0
    assert register(successor)['executable'] is False


@pytest.mark.parametrize('fault',['none','late_permission','readback'])
def test_successor_owner_transaction_rechecks_and_rolls_back(successor,monkeypatch,fault):
    """Real Owner transaction/SQL; current-release reader is a test boundary here."""
    from contextlib import contextmanager
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    case=successor;owner=case.db.owner
    owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(case.login)))
    for table in ('extension_runtime_outbox','extension_runtime_event'):
        owner.execute(sql.SQL('CREATE TABLE {}(org_id text,project_id text)').format(sql.Identifier(table)))
    for table in ('extension_runtime_operation','extension_runtime_outbox','extension_runtime_event'):
        owner.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        owner.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
    owner.execute('GRANT SELECT ON meta_membership TO aos_runtime')
    if fault=='late_permission':
        owner.execute("""CREATE FUNCTION revoke_successor_probe() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
            BEGIN DELETE FROM meta_membership WHERE org_id='org-a' AND project_id='project-a' AND subject='actor';RETURN NEW;END $$;
            CREATE TRIGGER revoke_successor_probe AFTER INSERT ON extension_dispatch_successor_registration_receipt
            FOR EACH ROW EXECUTE FUNCTION revoke_successor_probe();""")
    @contextmanager
    def connect():
        with psycopg.connect(**{**case.db.pg,'user':case.login},row_factory=dict_row,options='-c role=aos_runtime') as conn:
            yield conn
    service=object.__new__(FirstDispatchRegistrationService);service._connect=connect
    calls=[]
    def current(conn,**kwargs):
        calls.append(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx').fetchone())
        if not conn.execute("SELECT 1 FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s AND role='admin'",
                            (*kwargs['scope'].key,kwargs['actor'])).fetchone():
            raise PermissionError('current permission revoked')
    monkeypatch.setattr(service,'validate_current_authority_in_transaction',current)
    if fault=='readback':
        def corrupt(*args,**kwargs):raise ValueError('corrupt successor readback')
        monkeypatch.setattr('aos_api.ecommerce_growth_successor_registration.decode_successor_receipt',corrupt)
    request=SuccessorDispatchRegistrationRequest.model_validate(case.successor)
    if fault=='none':
        assert service.register_successor(scope=TenantScope('org-a','project-a'),request=request,actor='actor')['executable'] is False
        assert len(calls)==2 and calls[0]==calls[1]
    else:
        with pytest.raises((PermissionError,ValueError)):
            service.register_successor(scope=TenantScope('org-a','project-a'),request=request,actor='actor')
        assert owner.execute('SELECT count(*) AS n FROM extension_dispatch_successor_registration_receipt').fetchone()['n']==0
        assert owner.execute("SELECT count(*) AS n FROM meta_membership WHERE subject='actor'").fetchone()['n']==1
