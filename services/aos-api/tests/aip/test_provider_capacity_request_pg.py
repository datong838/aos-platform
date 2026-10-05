"""Original metadata inputs yield requests only, never physical capacity grants."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from pydantic import ValidationError
from aos_api.tenant_scope import TenantScope
from aos_api.db import connect

SCOPE = TenantScope('org-org', 'dev-project')

def body(provider=None, source=None):
    now = datetime.now(UTC)
    return dict(schemaVersion=1, tenant=dict(orgId='org-org', projectId='dev-project'),
        providerRef=provider or dict(assetType='ProviderInstanceRevision', assetId='provider', revision=1, contentHash='a'*64),
        physicalAccountId='dedicated-account', requestedMaxConcurrency=2,
        requestedMaxTokenUnits=20000, tokenUnit='token',
        basisKind='owner_requested_allocation',
        basisEvidenceRef=source or dict(assetType='EvidenceBundleRevision', assetId='source', revision=1, contentHash='b'*64),
        validFrom=now-timedelta(minutes=1), validUntil=now+timedelta(hours=1),
        proposalExpiresAt=now+timedelta(minutes=5))

@pytest.fixture
def original_inputs(https_signer):
    from tests.aip._runtime_guard_history_fixture import produce_formal_provider
    from tests.aip.test_evidence_bundle_provenance_pg import build_inputs, ACTOR
    from aos_api.auth import resolve_principal
    maker='capacity-maker-'+uuid4().hex
    provider=produce_formal_provider(SCOPE, maker, 'capacity-provider-'+uuid4().hex)
    store,key,request=build_inputs.__wrapped__()
    source=store.build_evidence_bundle(SCOPE,ACTOR,key,request)
    principal=resolve_principal(token=https_signer[0](maker), header_org=SCOPE.org_id,
                                header_project=SCOPE.project_id)
    return principal, provider, source


def test_original_capacity_request_persists_only_unapproved_immutable_terms(original_inputs):
    principal,provider,source=original_inputs
    from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore, ProviderCapacityRequestConflict
    request=ProviderCapacityRequest.model_validate(body(
        dict(assetType='ProviderInstanceRevision', assetId=provider.provider_instance_id,
             revision=provider.revision, contentHash=provider.content_hash),
        dict(assetType='EvidenceBundleRevision',assetId=source.bundle_id,
             revision=source.revision,contentHash=source.content_hash)))
    store=ProviderCapacityRequestStore();key='capacity-'+uuid4().hex
    before=None
    with connect(SCOPE) as conn:
        before={table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                for table in ('aip_model_capacity_reservation','aip_model_eval_budget_reservation')}
    saved=store.create(SCOPE, principal, key, request)
    assert saved['authorization_mode']=='REQUEST_ONLY_NO_CAPACITY_NO_START'
    assert saved['basis_verified'] is False and saved['execution_allowed'] is False
    assert saved['request_json']['makerSubject']==principal.subject
    assert store.create(SCOPE,principal,key,request)==saved
    with pytest.raises(ProviderCapacityRequestConflict):
        store.create(SCOPE,principal,key,request.model_copy(update={'requested_max_concurrency':3}))
    with connect(SCOPE) as conn:
        assert {table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in before}==before
    import psycopg
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect(SCOPE) as conn:
            conn.execute('UPDATE aip_provider_capacity_request SET created_by=created_by')
    with connect(TenantScope('dev-org','dev-project')) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_provider_capacity_request').fetchone()['n']==0


@pytest.mark.parametrize('field,value',[
    ('requestedMaxConcurrency',True),('requestedMaxConcurrency',0),
    ('requestedMaxTokenUnits',1.5),('tokenUnit','request'),('physicalAccountId',' account'),
    ('basisKind','supplier_verified'),('executionAllowed',True),('makerSubject','client'),
    ('proposalExpiresAt',datetime(2026,1,1)),('validUntil',datetime(2026,1,1,tzinfo=UTC)),
])
def test_capacity_request_rejects_client_authority_and_ambiguous_terms(field,value):
    from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
    raw=body();raw[field]=value
    with pytest.raises(ValidationError):ProviderCapacityRequest.model_validate(raw)


def exact_request(inputs):
    from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
    _, provider, source = inputs
    return ProviderCapacityRequest.model_validate(body(
        dict(assetType='ProviderInstanceRevision', assetId=provider.provider_instance_id,
             revision=provider.revision, contentHash=provider.content_hash),
        dict(assetType='EvidenceBundleRevision', assetId=source.bundle_id,
             revision=source.revision, contentHash=source.content_hash)))


def request_count():
    with connect(SCOPE) as conn:
        return conn.execute('SELECT count(*) AS n FROM aip_provider_capacity_request').fetchone()['n']


@pytest.mark.parametrize('fault', ['wrong_owner', 'provider_hash', 'basis_hash', 'expired', 'mutated_dto'])
def test_original_dependencies_reject_without_request_effect(original_inputs, https_signer, fault):
    from aos_api.auth import resolve_principal
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore, ProviderCapacityRequestBlocked
    principal, _, _ = original_inputs
    request = exact_request(original_inputs)
    if fault == 'wrong_owner':
        principal = resolve_principal(token=https_signer[0]('nonowner-'+uuid4().hex),
            header_org=SCOPE.org_id, header_project=SCOPE.project_id)
    elif fault == 'provider_hash':
        request = request.model_copy(update={'provider_ref': request.provider_ref.model_copy(update={'content_hash':'0'*64})})
    elif fault == 'basis_hash':
        request = request.model_copy(update={'basis_evidence_ref': request.basis_evidence_ref.model_copy(update={'content_hash':'0'*64})})
    elif fault == 'expired':
        now = datetime.now(UTC)
        request = request.model_copy(update={'valid_from':now-timedelta(minutes=5),
            'proposal_expires_at':now-timedelta(minutes=1)})
    else:
        request = request.model_copy(update={'requested_max_concurrency':True})
    before = request_count()
    with pytest.raises(ProviderCapacityRequestBlocked):
        ProviderCapacityRequestStore().create(SCOPE, principal, 'reject-'+uuid4().hex, request)
    assert request_count() == before


def test_idempotency_binds_actual_other_owner(original_inputs, https_signer):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.auth import resolve_principal
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore, ProviderCapacityRequestConflict
    principal, _, _ = original_inputs
    request = exact_request(original_inputs)
    store = ProviderCapacityRequestStore(); key = 'maker-bound-'+uuid4().hex
    first = store.create(SCOPE, principal, key, request)
    subject = 'other-owner-'+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')", (*SCOPE.key,subject))
    other = resolve_principal(token=https_signer[0](subject), header_org=SCOPE.org_id, header_project=SCOPE.project_id)
    before = request_count()
    with pytest.raises(ProviderCapacityRequestConflict): store.create(SCOPE, other, key, request)
    assert request_count() == before
    assert store.create(SCOPE, principal, key, request) == first


@pytest.mark.parametrize('fault', ['provider_head', 'basis_revoke'])
def test_original_dependency_change_blocks_replay(original_inputs, fault):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore, ProviderCapacityRequestBlocked
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import ACTOR
    principal, provider, source = original_inputs
    request = exact_request(original_inputs); store = ProviderCapacityRequestStore()
    key = 'dependency-replay-'+uuid4().hex
    store.create(SCOPE, principal, key, request); before = request_count()
    if fault == 'provider_head':
        with isolated_owner() as conn:
            conn.execute('UPDATE aip_provider_instance_head SET current_revision=current_revision+1 '
                'WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s', (*SCOPE.key,provider.provider_instance_id))
    else:
        AipProductionContractStore().revoke_evidence_bundle(SCOPE, ACTOR, source.bundle_id,
            'revoke-'+uuid4().hex, RevokeEvidenceBundleRequest(expectedRevision=source.revision,
                expectedContentHash=source.content_hash, reason='isolated capacity basis invalidation'))
    with pytest.raises(ProviderCapacityRequestBlocked): store.create(SCOPE, principal, key, request)
    assert request_count() == before


def test_sql_rls_flags_and_immutable_nonexecuting_request(original_inputs):
    import psycopg
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    principal, _, _ = original_inputs
    saved = ProviderCapacityRequestStore().create(SCOPE, principal, 'sql-bound-'+uuid4().hex, exact_request(original_inputs))
    with connect(SCOPE) as conn:
        flags = conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.aip_provider_capacity_request'::regclass").fetchone()
        assert flags == {'relrowsecurity':True, 'relforcerowsecurity':True}
    for statement in ('DELETE FROM aip_provider_capacity_request', 'TRUNCATE aip_provider_capacity_request'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connect(SCOPE) as conn: conn.execute(statement)
    for statement in ('UPDATE aip_provider_capacity_request SET created_by=created_by',
                      'DELETE FROM aip_provider_capacity_request', 'TRUNCATE aip_provider_capacity_request'):
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            with isolated_owner() as conn: conn.execute(statement)
    for column in ('basis_verified','execution_allowed'):
        with pytest.raises(psycopg.errors.CheckViolation):
            with connect(SCOPE) as conn:
                conn.execute(f"INSERT INTO aip_provider_capacity_request(org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at,{column}) "
                    f"SELECT org_id,project_id,%s,%s,request_hash,request_json,created_by,expires_at,true FROM aip_provider_capacity_request WHERE request_id=%s",
                    ('sql-reject-'+uuid4().hex, 'sql-key-'+uuid4().hex, saved['request_id']))
    with pytest.raises(psycopg.errors.CheckViolation):
        with connect(SCOPE) as conn:
            conn.execute("WITH original AS (SELECT *,request_json #- '{application,tenant}' AS bad FROM aip_provider_capacity_request WHERE request_id=%s) "
                "INSERT INTO aip_provider_capacity_request(org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at) "
                "SELECT org_id,project_id,%s,%s,encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(bad),'UTF8'),'sha256'),'hex'),bad,created_by,expires_at FROM original",
                (saved['request_id'], 'missing-tenant-'+uuid4().hex, 'missing-key-'+uuid4().hex))


@pytest.mark.parametrize('fault', ['missing_provider', 'unknown_field', 'zero_capacity', 'canary', 'boolean_capacity', 'fractional_tokens', 'excess_capacity', 'bad_version', 'blank_account', 'bad_ref_kind', 'bad_ref_revision', 'naive_window', 'extra_tenant', 'tab_account', 'newline_ref', 'unicode_account'])
def test_raw_runtime_cannot_insert_incomplete_or_canary_application(original_inputs, fault):
    import json
    import psycopg
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    principal, _, _ = original_inputs
    saved = ProviderCapacityRequestStore().create(SCOPE, principal, 'raw-base-'+uuid4().hex, exact_request(original_inputs))
    payload = saved['request_json']; scope = SCOPE
    if fault == 'missing_provider': del payload['application']['providerRef']
    elif fault == 'unknown_field': payload['application']['approval'] = 'client'
    elif fault == 'zero_capacity': payload['application']['requestedMaxConcurrency'] = 0
    elif fault == 'boolean_capacity': payload['application']['requestedMaxConcurrency'] = True
    elif fault == 'fractional_tokens': payload['application']['requestedMaxTokenUnits'] = 1.5
    elif fault == 'excess_capacity': payload['application']['requestedMaxConcurrency'] = 1000001
    elif fault == 'bad_version': payload['application']['schemaVersion'] = True
    elif fault == 'blank_account': payload['application']['physicalAccountId'] = ' account'
    elif fault == 'bad_ref_kind': payload['application']['providerRef']['assetType'] = 'ModelRevision'
    elif fault == 'bad_ref_revision': payload['application']['basisEvidenceRef']['revision'] = 0
    elif fault == 'naive_window': payload['application']['validUntil'] = payload['application']['validUntil'][:-6]
    elif fault == 'tab_account': payload['application']['physicalAccountId'] = '\taccount'
    elif fault == 'newline_ref': payload['application']['providerRef']['assetId'] = 'provider\n'
    elif fault == 'unicode_account': payload['application']['physicalAccountId'] = '\u3000account'
    elif fault == 'extra_tenant': payload['application']['tenant']['unexpected'] = 'client'
    else:
        scope = TenantScope('dev-org','dev-project')
        payload['application']['tenant']['orgId'] = scope.org_id
    before = request_count()
    with pytest.raises(psycopg.errors.CheckViolation):
        with connect(scope) as conn:
            conn.execute("WITH terms AS (SELECT %s::jsonb AS body) INSERT INTO aip_provider_capacity_request "
                "(org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at) "
                "SELECT %s,%s,%s,%s,encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8'),'sha256'),'hex'),body,%s,%s FROM terms",
                (json.dumps(payload), *scope.key, 'raw-'+uuid4().hex, 'raw-key-'+uuid4().hex, principal.subject, saved['expires_at']))
    assert request_count() == before
    with connect(TenantScope('dev-org','dev-project')) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_provider_capacity_request').fetchone()['n'] == 0
