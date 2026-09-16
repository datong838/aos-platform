"""Native PG structural history, with explicit non-executed activation fixture."""
from copy import deepcopy
from uuid import UUID,uuid4
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

pytest_plugins=('test_product_event_control_host_service',)
from tests.test_ecommerce_dispatch_configuration_receipt import row
from aos_api.ecommerce_dispatch_configuration_receipt import receipt_body,decode_receipt
from aos_api.asset_registry.canonical_json import canonical_sha256

TABLE='public.extension_dispatch_configuration_refresh_receipt'


def insert(c,value,table=TABLE):
    return c.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
        sql.SQL(table),sql.SQL(',').join(map(sql.Identifier,value)),sql.SQL(',').join(sql.Placeholder() for _ in value)),
        tuple(Jsonb(v) if isinstance(v,(dict,list)) else v for v in value.values())).fetchone()


@pytest.fixture
def ledger(host_case):
    c,_,_,dispatch,_=host_case
    c.execute('RESET ROLE')
    saved=row();req=saved['request']
    saved.update(installation_id=dispatch.installation_id,generation=dispatch.generation)
    req['installationRef']['installationId']=str(dispatch.installation_id);req['generation']=str(dispatch.generation)
    # Structural FK parents only. No actual configure, enable, dispatch or source
    # execution is claimed; the future Owner must verify original resume evidence.
    operation=dict(org_id=saved['org_id'],project_id=saved['project_id'],cutover_operation_id=saved['activation_operation_id'],
        kind='activate',idempotency_key='named-ledger-root',request_hash='sha256:'+'a'*64,status='resumed',
        cutover_group_id=saved['cutover_group_id'],expected_group_revision=29,target_group_revision=30,
        target_installation_id=dispatch.installation_id,target_generation=dispatch.generation,
        target_execution_epoch=3,target_runtime_revision=6,operation_ids=req['operationIds'],old_dispatch_snapshot=[],
        new_dispatch_snapshot=[],checkpoint={},pending_target_receipt_refs=[],policy_ref={},approval_ref={},requested_by='fixture-admin')
    insert(c,operation,'public.extension_dispatch_cutover_operation')
    insert(c,dict(org_id=saved['org_id'],project_id=saved['project_id'],receipt_id=saved['activation_resume_receipt_id'],
        cutover_operation_id=saved['activation_operation_id'],phase='resume',request_hash='sha256:'+'a'*64,
        authority_data={'fixture':'structural only'},content_hash=req['sourceAuthorityRef']['contentHash']),
        'public.extension_dispatch_cutover_receipt')
    saved['request_hash']=canonical_sha256(req);saved['body']=receipt_body(saved);saved['content_hash']=canonical_sha256(saved['body'])
    yield c,saved


def test_native_hash_projection_and_original_parent(ledger):
    c,saved=ledger
    result=insert(c,saved)
    assert decode_receipt(result)['body']==saved['body']
    assert c.execute('SELECT canonical_bundle_control_sha256(%s) AS hash',(Jsonb(saved['body']),)).fetchone()['hash']==saved['content_hash']


@pytest.mark.parametrize('role',['aos_runtime','aos_extension_maintainer'])
def test_application_roles_cannot_insert_even_valid_history(ledger,role):
    c,saved=ledger
    c.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
    with pytest.raises(psycopg.errors.InsufficientPrivilege),c.transaction():insert(c,saved)
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==0


@pytest.mark.parametrize('verb',['UPDATE','DELETE','TRUNCATE'])
def test_history_is_immutable_even_for_owner(ledger,verb):
    c,saved=ledger;insert(c,saved)
    statement={'UPDATE':'UPDATE '+TABLE+' SET actor=actor','DELETE':'DELETE FROM '+TABLE,'TRUNCATE':'TRUNCATE '+TABLE}[verb]
    with pytest.raises(psycopg.Error),c.transaction():c.execute(statement)
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==1


@pytest.mark.parametrize('dimension',['org_id','project_id'])
def test_tenant_rls_hides_populated_history(ledger,dimension):
    c,saved=ledger;insert(c,saved)
    c.execute('SET LOCAL ROLE aos_runtime')
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==1
    c.execute("SELECT set_config(%s,%s,true)",('aos.'+dimension,'dev-org' if dimension=='org_id' else 'another-project'))
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==0


@pytest.mark.parametrize('fault',['request-hash','body-hash','missing-root','different-group','wrong-predecessor'])
def test_forged_or_incomplete_structural_history_rejected(ledger,fault):
    c,saved=ledger;saved=deepcopy(saved)
    if fault=='request-hash':saved['request_hash']='sha256:'+'e'*64
    elif fault=='body-hash':saved['content_hash']='sha256:'+'f'*64
    elif fault=='missing-root':saved['activation_resume_receipt_id']=uuid4()
    elif fault=='different-group':
        saved['cutover_group_id']=uuid4();saved['request']['cutoverGroupId']=str(saved['cutover_group_id'])
    else:saved['request']['sourceAuthorityRef']['contentHash']='sha256:'+'d'*64
    if fault not in ('request-hash','body-hash'):
        saved['request_hash']=canonical_sha256(saved['request']);saved['body']=receipt_body(saved);saved['content_hash']=canonical_sha256(saved['body'])
    with pytest.raises(psycopg.errors.CheckViolation),c.transaction():insert(c,saved)
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==0


def successor(saved):
    value=deepcopy(saved);req=value['request']
    value.update(receipt_id=uuid4(),revision=2,previous_receipt_id=saved['receipt_id'],previous_hash=saved['content_hash'])
    req.update(sourceAuthorityRef=decode_receipt(saved)['ref'],expectedGroupRevision=req['expectedGroupRevision']+1,
        sourceRuntimeRevision=req['targetRuntimeRevision'],sourceExecutionEpoch=req['targetExecutionEpoch'],
        sourceConfigurationRef=deepcopy(req['targetConfigurationRef']),
        targetRuntimeRevision=req['targetRuntimeRevision']+3,targetExecutionEpoch=req['targetExecutionEpoch']+2,
        idempotencyKey='second-refresh',configureOperationId=str(uuid4()),enableOperationId=str(uuid4()))
    req['targetConfigurationRef'].update(revision=3,hash='sha256:'+'e'*64)
    value['idempotency_key']=req['idempotencyKey']
    value['request_hash']=canonical_sha256(req);value['body']=receipt_body(value);value['content_hash']=canonical_sha256(value['body'])
    return value


def test_same_family_history_chain_and_duplicate_key(ledger):
    c,saved=ledger;insert(c,saved);second=successor(saved)
    assert decode_receipt(insert(c,second))['ref']['revision']==2
    with pytest.raises(psycopg.errors.UniqueViolation),c.transaction():insert(c,second)
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==2


@pytest.mark.parametrize('field',['sourceRuntimeRevision','sourceExecutionEpoch','sourceConfigurationRef','expectedGroupRevision'])
def test_chain_cannot_skip_previous_target_even_with_valid_hashes(ledger,field):
    c,saved=ledger;insert(c,saved);second=successor(saved)
    if field=='sourceConfigurationRef':second['request'][field]['hash']='sha256:'+'f'*64
    else:second['request'][field]-=1
    second['request_hash']=canonical_sha256(second['request']);second['body']=receipt_body(second);second['content_hash']=canonical_sha256(second['body'])
    with pytest.raises(psycopg.errors.CheckViolation),c.transaction():insert(c,second)
    assert c.execute('SELECT count(*) AS n FROM '+TABLE).fetchone()['n']==1
