"""Actual signed-document registration, separate from Source issuance authority."""
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourcePolicy, SupplierCapacityAttestation
from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit
from tests.aip.test_provider_capacity_publication_pg import source_policy, supplier_attestation, permit
from tests.aip.test_capacity_publication_registry_pg import committed_native_registry

KINDS = {'policy': ('ProviderCapacitySourcePolicyRevision', source_policy, ProviderCapacitySourcePolicy),
    'attestation': ('SupplierCapacityAttestationRevision', supplier_attestation, SupplierCapacityAttestation),
    'permit': ('ProviderCapacitySigningPermitRevision', permit, ProviderCapacitySigningPermit)}


def prepared_document(f, kind='policy', fault=None):
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from aos_api.aip_provider_capacity_document_registry import install_document_registry
    public = f['sign_key'].public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    origin = json.loads(f['body'])
    asset_type, factory, model = KINDS[kind]
    payload = factory()
    if fault == 'max_revision':
        import random
        rng = random.Random(731)
        payload['revision'] = int('9'+''.join(str(rng.randrange(10)) for _ in range(4299)))
    if kind != 'attestation':
        payload['deploymentTarget'] = dict(origin['deploymentTarget'])
        if fault == 'deployment': payload['deploymentTarget']['databaseOid'] += 1
    if fault == 'expired_document':
        payload.update(validFrom=datetime.now(UTC)-timedelta(minutes=2), validUntil=datetime.now(UTC)-timedelta(minutes=1))
    document = model.model_validate(payload)
    parsed = document.model_dump(mode='json', by_alias=True)
    if fault == 'purpose': parsed['purpose'] = 'wrong-purpose'
    raw = canonical_json(parsed)
    digest = hashlib.sha256(raw).hexdigest()
    root = dict(publisher=document.publisher, keyId=document.key_id, algorithm='Ed25519',
        publicKey=base64.b64encode(public).decode(), revision='sha256:'+'a'*64,
        notBefore='2020-01-01T00:00:00+00:00', notAfter='2030-01-01T00:00:00+00:00', revokedAt=None)
    if fault == 'unknown_root': root['keyId'] = 'different-approved-root'
    if fault == 'revoked_root': root['revokedAt'] = '2020-01-01T00:00:00+00:00'
    if fault == 'expired_root': root['notAfter'] = '2021-01-01T00:00:00+00:00'
    roots = json.dumps(dict(trustRoots=[root]), sort_keys=True, separators=(',', ':')).encode('ascii')
    origin['rootSnapshotHash'] = 'sha256:'+hashlib.sha256(roots).hexdigest()
    origin['allowedDocumentRefs'] = [dict(assetType=asset_type,
        assetId=document.asset_id, revision=document.revision,
        contentHash='0'*64 if fault == 'allowed_ref' else digest)]
    alternate = None
    if fault == 'identity_drift':
        alternate_payload = document.model_dump(by_alias=True)
        alternate_payload['validUntil'] = document.valid_until + timedelta(seconds=1)
        alternate_document = model.model_validate(alternate_payload)
        alternate_raw = canonical_json(alternate_document.model_dump(mode='json', by_alias=True))
        alternate_signature = f['sign_key'].sign(alternate_raw)
        alternate_hash = hashlib.sha256(alternate_raw).hexdigest()
        origin['allowedDocumentRefs'].append(dict(assetType=asset_type,
            assetId=document.asset_id, revision=document.revision, contentHash=alternate_hash))
        alternate = "SELECT aos_capacity_publication_private.register_document('%s',decode('%s','hex'),decode('%s','hex'));" % (asset_type, alternate_raw.hex(), alternate_signature.hex())
    if fault == 'allowed_id': origin['allowedDocumentRefs'][0]['assetId'] = 'different-approved-id'
    if fault == 'allowed_revision': origin['allowedDocumentRefs'][0]['revision'] += 1
    if fault == 'allowed_kind': origin['allowedDocumentRefs'][0]['assetType'] = 'SupplierCapacityAttestationRevision'
    body = canonical_json(origin)
    signature = f['sign_key'].sign(body)
    ddl = []
    install_document_registry(ddl.append)
    f['run']('BEGIN;'+'\n'.join(s.rstrip().rstrip(';')+';' for s in ddl)+'COMMIT;')
    call = "SELECT aos_capacity_publication_private.register_origin(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));" % (body.hex(), signature.hex(), roots.hex())
    assert f['run'](f['begin']+call+'COMMIT;').stdout.strip() == hashlib.sha256(body).hexdigest()
    document_signature = f['sign_key'].sign(raw)
    if fault == 'signature': document_signature = bytes([document_signature[0]^1])+document_signature[1:]
    register = "SELECT aos_capacity_publication_private.register_document('%s',decode('%s','hex'),decode('%s','hex'));" % (asset_type, raw.hex(), document_signature.hex())
    return dict(raw=raw, signature=document_signature, digest=digest, origin_hash=hashlib.sha256(body).hexdigest(), register=register, alternate=alternate)


@pytest.mark.parametrize('kind', list(KINDS))
def test_signed_document_actual_commit_under_bootstrap_allowlist(committed_native_registry, kind):
    f = committed_native_registry
    run = f['run']
    d = prepared_document(f, kind)
    assert run(f['begin']+d['register']+'ROLLBACK;').stdout.strip() == d['digest']
    assert run('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '0'
    assert run(f['begin']+d['register']+'COMMIT;').stdout.strip() == d['digest']
    stored = run("SELECT encode(raw_body,'hex'),encode(signature,'hex'),origin_hash,origin_epoch,root_ordinal FROM aos_capacity_publication_private.document;").stdout.strip().split('|')
    assert stored == [d['raw'].hex(), d['signature'].hex(), d['origin_hash'], '1', '1']
    assert run(f['begin']+d['register']+'COMMIT;').stdout.strip() == d['digest']
    assert run('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '1'
    print('CAPACITY_DOCUMENT_COMMIT_PROOF '+f['database']+' kind='+kind+' rollback=empty commit=exact replay=single source_issuance=false')


@pytest.mark.parametrize('fault', ['signature','allowed_ref','allowed_id','allowed_revision','allowed_kind','unknown_root','revoked_root','expired_root',
    'expired_document','deployment','purpose','canary','session','epoch'])
def test_signed_allowed_document_single_fault_rejected(committed_native_registry, fault):
    f = committed_native_registry
    d = prepared_document(f, fault=fault)
    begin = f['begin']
    if fault == 'canary': begin = begin.replace("aos.org_id='org-org'", "aos.org_id='dev-org'")
    if fault == 'session': begin = begin.replace('SET SESSION AUTHORIZATION aos_provider_capacity_policy_publisher;', '')
    if fault == 'epoch': f['run']('UPDATE aos_capacity_publication_private.registry_epoch SET epoch=2;')
    result = f['run'](begin+d['register']+'COMMIT;', success=False)
    expected = 'CAPACITY_SOURCE_POLICY_REQUIRED' if fault == 'purpose' else 'CAPACITY_DOCUMENT_REGISTRATION_DENIED'
    assert expected in result.stderr, result.stderr
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '0'
    assert f['run']('SELECT epoch FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == ('2' if fault == 'epoch' else '1')
    print('CAPACITY_DOCUMENT_NEGATIVE_PROOF '+f['database']+' fault='+fault+' bootstrap_signed=true signature_valid='+str(fault!='signature').lower()+' exact_ref_allowed='+str(not fault.startswith('allowed_')).lower()+' rows=0')


def test_document_acl_catalog_and_direct_paths(committed_native_registry):
    f = committed_native_registry
    d = prepared_document(f)
    for role in ['aos_runtime','aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher']:
        acl = f['run']("SELECT has_table_privilege('%s','aos_capacity_publication_private.document','SELECT,INSERT,UPDATE,DELETE,TRUNCATE'),has_function_privilege('%s','aos_capacity_publication_private.read_source_policy(bytea)','EXECUTE');" % (role,role))
        assert acl.stdout.strip() == 'f|f'
        result = f['run']('BEGIN; SET SESSION AUTHORIZATION '+role+'; SELECT * FROM aos_capacity_publication_private.document; COMMIT;', success=False)
        assert 'permission denied' in result.stderr
        if role != 'aos_provider_capacity_policy_publisher':
            result = f['run']('BEGIN; SET SESSION AUTHORIZATION '+role+';'+d['register']+'COMMIT;', success=False)
            assert 'permission denied' in result.stderr
    assert f['run']("SELECT relrowsecurity,relforcerowsecurity,relowner='aos_capacity_publication_owner'::regrole FROM pg_class WHERE oid='aos_capacity_publication_private.document'::regclass;").stdout.strip() == 't|t|t'
    assert f['run']("SELECT prosecdef,proowner='aos_capacity_publication_owner'::regrole,proconfig FROM pg_proc WHERE oid='aos_capacity_publication_private.register_document(text,bytea,bytea)'::regprocedure;").stdout.strip() == 't|t|{search_path=pg_catalog}'


def test_document_immutable_and_owner_tenant_rls(committed_native_registry):
    f = committed_native_registry
    d = prepared_document(f)
    f['run'](f['begin']+d['register']+'COMMIT;')
    for mutation in ['UPDATE aos_capacity_publication_private.document SET revision=revision;',
        'DELETE FROM aos_capacity_publication_private.document;']:
        result = f['run']('BEGIN;'+mutation+'COMMIT;', success=False)
        assert 'CAPACITY_PUBLICATION_IMMUTABLE' in result.stderr
    for org, count in [('org-org','1'),('dev-org','0')]:
        assert f['run']("BEGIN; SET LOCAL ROLE aos_capacity_publication_owner; SET LOCAL aos.org_id='%s'; SET LOCAL aos.project_id='dev-project'; SELECT count(*) FROM aos_capacity_publication_private.document; ROLLBACK;" % org).stdout.strip() == count
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '1'


def test_document_verifier_owner_drift_rejected_without_repair(committed_native_registry):
    f = committed_native_registry
    d = prepared_document(f)
    result = f['run']('BEGIN; ALTER FUNCTION aos_ed25519.verify(bytea,bytea,bytea) OWNER TO aos_app;'
        +f['begin'].removeprefix('BEGIN;')+d['register']+'COMMIT;', success=False)
    assert 'CAPACITY_ORIGIN_VERIFIER_REQUIRED' in result.stderr
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '0'
    assert f['run']("SELECT proowner='aos_ed25519_owner'::regrole FROM pg_proc WHERE oid='aos_ed25519.verify(bytea,bytea,bytea)'::regprocedure;").stdout.strip() == 't'


@pytest.mark.parametrize('order', ['registrar_first', 'writer_first'])
def test_document_epoch_actual_commit_competition(committed_native_registry, order):
    import time
    from tests.aip.test_capacity_publication_registry_pg import _NativeSqlSession
    f = committed_native_registry
    d = prepared_document(f)
    f['run'](f['begin']+d['register']+'COMMIT;')
    registrar = _NativeSqlSession(f['command'])
    writer = _NativeSqlSession(f['command'])
    try:
        registrar.send(f['begin']+"SELECT pg_backend_pid();")
        rpid = int(registrar.line())
        writer.send("BEGIN; SET LOCAL statement_timeout='10s'; SELECT pg_backend_pid();")
        wpid = int(writer.line())
        change = "UPDATE aos_capacity_publication_private.registry_epoch SET epoch=2; SELECT 'writer-ready';"
        if order == 'registrar_first':
            registrar.send(d['register'])
            assert registrar.line() == d['digest']
            writer.send(change)
            holding, waiting = rpid, wpid
        else:
            writer.send(change)
            assert writer.line() == 'writer-ready'
            registrar.send(d['register'])
            holding, waiting = wpid, rpid
        deadline = time.monotonic()+4
        blocked = False
        while time.monotonic() < deadline:
            if f['run']('SELECT %s=ANY(pg_blocking_pids(%s));' % (holding,waiting)).stdout.strip() == 't':
                blocked = True
                break
            time.sleep(.03)
        assert blocked
        if order == 'registrar_first':
            registrar.send("COMMIT; SELECT 'registrar-committed';")
            assert registrar.line() == 'registrar-committed'
            assert writer.line() == 'writer-ready'
            writer.send("COMMIT; SELECT 'writer-committed';")
            assert writer.line() == 'writer-committed'
        else:
            writer.send("COMMIT; SELECT 'writer-committed';")
            assert writer.line() == 'writer-committed'
            assert registrar.lines.get(timeout=12) is None
            assert registrar.process.wait(timeout=5) != 0
            assert 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' in ''.join(registrar.errors)
        assert f['run']('SELECT epoch FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '2'
        assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '1'
        failure = f['run'](f['begin']+d['register']+'COMMIT;', success=False)
        assert 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' in failure.stderr
        print('CAPACITY_DOCUMENT_EPOCH_PROOF '+f['database']+' order='+order+' blocked=true epoch=2 retained_rows=1 administrative_invalidation_only=true')
    finally:
        for session in (registrar,writer):
            try: session.send('ROLLBACK;')
            except (BrokenPipeError,ValueError): pass
        registrar.close()
        writer.close()


def test_document_original_4300_digit_revision_real_commit(committed_native_registry):
    f = committed_native_registry
    d = prepared_document(f, fault='max_revision')
    assert f['run'](f['begin']+d['register']+'COMMIT;').stdout.strip() == d['digest']
    assert f['run']("SELECT length(revision),encode(raw_body,'hex') FROM aos_capacity_publication_private.document;").stdout.strip() == '4300|'+d['raw'].hex()
    assert f['run'](f['begin']+d['register']+'COMMIT;').stdout.strip() == d['digest']
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '1'
    print('CAPACITY_DOCUMENT_MAX_REVISION_PROOF '+f['database']+' digits=4300 original_bytes=true committed=true replay=single')


@pytest.mark.parametrize('kind', list(KINDS))
def test_signed_bootstrap_rejects_two_originals_same_identity(committed_native_registry, kind):
    f = committed_native_registry
    with pytest.raises(AssertionError, match='CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED'):
        prepared_document(f, kind=kind, fault='identity_drift')
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin;').stdout.strip() == '0'
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '0'
    print('CAPACITY_DOCUMENT_DUPLICATE_BOOTSTRAP_PROOF '+f['database']+' kind='+kind+' both_signed=true duplicate_identity_denied=true rows=0')


@pytest.mark.parametrize('kind', list(KINDS))
def test_document_physical_identity_constraint_preserves_original(committed_native_registry, kind):
    f = committed_native_registry
    d = prepared_document(f, kind=kind)
    assert f['run'](f['begin']+d['register']+'COMMIT;').stdout.strip() == d['digest']
    original = KINDS[kind][2].model_validate(json.loads(d['raw']))
    payload = original.model_dump(by_alias=True)
    payload['validUntil'] = original.valid_until + timedelta(seconds=1)
    raw = canonical_json(KINDS[kind][2].model_validate(payload).model_dump(mode='json', by_alias=True))
    signature = f['sign_key'].sign(raw)
    digest = hashlib.sha256(raw).hexdigest()
    # Administrative fixture exercises storage only; it is not an allowed registration.
    insert = "INSERT INTO aos_capacity_publication_private.document SELECT org_id,project_id,'%s',kind,asset_id,revision,identity_hash,decode('%s','hex'),decode('%s','hex'),origin_hash,origin_epoch,snapshot_hash,root_ordinal FROM aos_capacity_publication_private.document;" % (digest,raw.hex(),signature.hex())
    failure = f['run']('BEGIN;'+insert+'COMMIT;', success=False)
    assert 'duplicate key value violates unique constraint' in failure.stderr, failure.stderr
    preserved = f['run']("SELECT content_hash,encode(raw_body,'hex'),encode(signature,'hex') FROM aos_capacity_publication_private.document;").stdout.strip()
    assert preserved == '|'.join([d['digest'], d['raw'].hex(), d['signature'].hex()])
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '1'
    print('CAPACITY_DOCUMENT_IDENTITY_PROOF '+f['database']+' kind='+kind+' administrative_storage_only=true second_rejected=true original_preserved=true')
