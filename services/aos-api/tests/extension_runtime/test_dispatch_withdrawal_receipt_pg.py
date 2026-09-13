import importlib.util
from types import SimpleNamespace
from uuid import uuid4
from copy import deepcopy
import psycopg
import pytest
from psycopg.types.json import Jsonb
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest, preview_registration
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from test_dispatch_registration_receipt_pg import receipt_db, database, pytestmark, ROOT
from test_ecommerce_growth_registration_contracts import payload


@pytest.fixture
def withdrawal_db(receipt_db):
    db,installation,generation=receipt_db
    raw=payload();raw['installationRef']['installationId']=str(installation);raw['generation']=str(generation)
    request=FirstDispatchRegistrationRequest.model_validate(raw)
    original=dict(schemaVersion='aos.ecommerce.first-dispatch-registration-receipt/v1',
        tenant=dict(orgId='org-a',projectId='project-a'),receiptId=str(uuid4()),
        installationId=str(installation),generation=str(generation),groupId=raw['groupId'],
        requestHash=request.request_hash(),idempotencyKey=raw['idempotencyKey'],actor='actor',request=raw,
        dispatchSnapshot=preview_registration(request)['proposedDispatchSnapshot'],executable=False,
        createdAt='2026-09-13T00:00:00+00:00')
    digest=canonical_sha256(original)
    db.owner.execute('''INSERT INTO extension_dispatch_registration_receipt
        (org_id,project_id,receipt_id,installation_id,generation,group_id,idempotency_key,request_hash,payload,content_hash)
        VALUES('org-a','project-a',%s,%s,%s,%s,%s,%s,%s,%s)''',
        (original['receiptId'],installation,generation,original['groupId'],raw['idempotencyKey'],request.request_hash(),Jsonb(original),digest))
    path=ROOT/'alembic/versions/a0v_029_dispatch_withdrawal_receipt.py'
    spec=importlib.util.spec_from_file_location('withdrawal_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=db.owner.execute);module.upgrade()
    ref=dict(resourceType='FirstDispatchRegistrationReceipt',resourceId=original['receiptId'],revision=1,contentHash=digest)
    command=RegistrationWithdrawalRequest(registrationReceiptRef=ref,expectedInstallationEtag=5,idempotencyKey='withdraw-1')
    body=dict(schemaVersion='aos.ecommerce.first-dispatch-withdrawal-receipt/v1',
        tenant=original['tenant'],receiptId=str(uuid4()),registrationReceiptRef=ref,
        installationId=str(installation),generation=str(generation),groupId=raw['groupId'],
        idempotencyKey=command.idempotencyKey,requestHash=command.request_hash(),actor='actor',
        request=command.model_dump(mode='json'),oldDispatchSnapshot=original['dispatchSnapshot'],
        releasedOperationCount=9,executable=False,createdAt='2026-09-13T01:00:00+00:00')
    return db,body


def insert(case,body=None):
    db,original=case;body=body or original
    db.owner.execute('''INSERT INTO extension_dispatch_withdrawal_receipt
        (org_id,project_id,receipt_id,registration_receipt_id,idempotency_key,request_hash,payload,content_hash)
        VALUES('org-a','project-a',%s,%s,%s,%s,%s,%s)''',
        (body['receiptId'],original['registrationReceiptRef']['resourceId'],body['idempotencyKey'],body['requestHash'],Jsonb(body),canonical_sha256(body)))


def test_valid_receipt_and_uniqueness(withdrawal_db):
    insert(withdrawal_db)
    with pytest.raises(psycopg.errors.UniqueViolation): insert(withdrawal_db)
    body=deepcopy(withdrawal_db[1]);body['receiptId']=str(uuid4());body['idempotencyKey']='withdraw-2'
    body['request']['idempotencyKey']='withdraw-2';body['requestHash']=canonical_sha256(body['request'])
    with pytest.raises(psycopg.errors.UniqueViolation): insert(withdrawal_db,body)


@pytest.mark.parametrize('mutation',['tenant','reference','snapshot','count','executable','request','actor','schema','extra'])
def test_rehashed_corruption_rejected(withdrawal_db,mutation):
    body=deepcopy(withdrawal_db[1])
    if mutation=='tenant':body['tenant']['orgId']='other'
    elif mutation=='reference':body['registrationReceiptRef']['contentHash']='sha256:'+'0'*64
    elif mutation=='snapshot':body['oldDispatchSnapshot'][0]['revision']=2
    elif mutation=='count':body['releasedOperationCount']=True
    elif mutation=='executable':body['executable']=True
    elif mutation=='request':body['request']['expectedInstallationEtag']=6
    elif mutation=='actor':body['actor']=' '
    elif mutation=='schema':body['schemaVersion']='other'
    else:body['unexpected']='no'
    with pytest.raises(psycopg.Error):insert(withdrawal_db,body)
    assert withdrawal_db[0].owner.execute('SELECT count(*) AS n FROM extension_dispatch_withdrawal_receipt').fetchone()['n']==0


@pytest.mark.parametrize('action',['UPDATE extension_dispatch_withdrawal_receipt SET content_hash=content_hash',
    'DELETE FROM extension_dispatch_withdrawal_receipt','TRUNCATE extension_dispatch_withdrawal_receipt'])
def test_owner_cannot_rewrite_history(withdrawal_db,action):
    insert(withdrawal_db)
    with pytest.raises(psycopg.Error):withdrawal_db[0].owner.execute(action)


def test_tenant_read_and_no_direct_write_roles(withdrawal_db):
    insert(withdrawal_db);db=withdrawal_db[0]
    with psycopg.connect(**db.pg,autocommit=True) as conn:
        conn.execute('SET ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id','org-a',false),set_config('aos.project_id','project-a',false)")
        assert conn.execute('SELECT count(*) FROM extension_dispatch_withdrawal_receipt').fetchone()[0]==1
        conn.execute("SELECT set_config('aos.org_id','other',false)")
        assert conn.execute('SELECT count(*) FROM extension_dispatch_withdrawal_receipt').fetchone()[0]==0
        for role in ('aos_runtime','aos_extension_maintainer'):
            for action in ('INSERT','UPDATE','DELETE','TRUNCATE'):
                assert conn.execute("SELECT has_table_privilege(%s,'extension_dispatch_withdrawal_receipt',%s)",(role,action)).fetchone()[0] is False


@pytest.mark.parametrize('revision',[True,0,-1,2**63,'5'])
def test_invalid_request_revision_even_with_fresh_hash(withdrawal_db,revision):
    body=deepcopy(withdrawal_db[1]);body['request']['expectedInstallationEtag']=revision
    body['requestHash']=canonical_sha256(body['request'])
    with pytest.raises(psycopg.Error):insert(withdrawal_db,body)


def test_fractional_origin_ref_rejected_even_with_new_hash(withdrawal_db):
    body=deepcopy(withdrawal_db[1]);body['registrationReceiptRef']['revision']=1.0
    body['request']['registrationReceiptRef']['revision']=1.0
    body['requestHash']=canonical_sha256(body['request'])
    with pytest.raises(psycopg.Error):insert(withdrawal_db,body)
