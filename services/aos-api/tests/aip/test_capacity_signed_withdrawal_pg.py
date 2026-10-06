"""Independent signed withdrawal; preserved history is never a Source grant."""
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from aos_api.asset_registry.canonical_json import canonical_json
from tests.aip.test_capacity_publication_registry_pg import committed_native_registry
from tests.aip.test_capacity_document_registry_pg import prepared_document


def prepared_withdrawal(f, fault=None):
    from aos_api.aip_provider_capacity_withdrawal_contracts import ProviderCapacityOriginWithdrawal
    from aos_api.aip_provider_capacity_withdrawal_registry import install_withdrawal_registry
    document = prepared_document(f)
    f['run'](f['begin']+document['register']+'COMMIT;')
    original = json.loads(f['run']("SELECT convert_from(raw_body,'UTF8') FROM aos_capacity_publication_private.origin;").stdout)
    payload = dict(schemaVersion=1,tenant=original['tenant'],assetId='signed-origin-withdrawal',revision=1,
        publisher=original['publisher'],keyId=original['keyId'],validFrom=datetime.now(UTC)-timedelta(minutes=1),
        validUntil=datetime.now(UTC)+timedelta(minutes=10),deploymentTarget=original['deploymentTarget'],
        purpose='provider_capacity_origin_withdrawal',anchorRevision=original['anchorRevision'],
        publisherSubject=original['publisherSubject'],policyPublisherRole=original['policyPublisherRole'],
        originRef=dict(assetType='ProviderCapacityOriginBootstrapRevision',assetId=original['assetId'],
            revision=original['revision'],contentHash=document['origin_hash']),expectedEpoch=1)
    if fault == 'publisher': payload['publisher'] = 'other-authority'
    if fault == 'key': payload['keyId'] = 'other-authority-key'
    if fault == 'subject': payload['publisherSubject'] = 'other-subject'
    if fault == 'anchor': payload['anchorRevision'] = 'sha256:'+'d'*64
    if fault == 'origin_hash': payload['originRef']['contentHash'] = '0'*64
    if fault == 'origin_id': payload['originRef']['assetId'] = 'other-origin'
    if fault == 'origin_revision': payload['originRef']['revision'] += 1
    if fault == 'deployment': payload['deploymentTarget'] = dict(payload['deploymentTarget'],databaseOid=payload['deploymentTarget']['databaseOid']+1)
    if fault == 'epoch': payload['expectedEpoch'] = 2
    if fault == 'expired': payload.update(validFrom=datetime.now(UTC)-timedelta(minutes=2),validUntil=datetime.now(UTC)-timedelta(minutes=1))
    if fault == 'future': payload.update(validFrom=datetime.now(UTC)+timedelta(minutes=1),validUntil=datetime.now(UTC)+timedelta(minutes=2))
    raw = canonical_json(ProviderCapacityOriginWithdrawal.model_validate(payload).model_dump(mode='json',by_alias=True))
    if fault in ('purpose','extra','null','epoch_bool','schema_bool','epoch_zero','epoch_overflow','origin_revision_bool','tenant','long_window'):
        mutated = json.loads(raw)
        if fault == 'purpose': mutated['purpose'] = 'provider_capacity_origin_bootstrap'
        if fault == 'extra': mutated['verified'] = True
        if fault == 'null': mutated['publisherSubject'] = None
        if fault == 'epoch_bool': mutated['expectedEpoch'] = True
        if fault == 'schema_bool': mutated['schemaVersion'] = True
        if fault == 'epoch_zero': mutated['expectedEpoch'] = 0
        if fault == 'epoch_overflow': mutated['expectedEpoch'] = 9223372036854775807
        if fault == 'origin_revision_bool': mutated['originRef']['revision'] = True
        if fault == 'tenant': mutated['tenant']['orgId'] = 'dev-org'
        if fault == 'long_window': mutated['validUntil'] = (datetime.fromisoformat(mutated['validFrom'])+timedelta(days=367)).isoformat().replace('+00:00','Z')
        raw = canonical_json(mutated)
    signature = f['sign_key'].sign(raw)
    if fault == 'signature': signature = bytes([signature[0]^1])+signature[1:]
    if fault == 'foreign_signer':
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        signature = Ed25519PrivateKey.generate().sign(raw)
    ddl = []
    install_withdrawal_registry(ddl.append)
    f['run']('BEGIN;'+'\n'.join(s.rstrip().rstrip(';')+';' for s in ddl)+'COMMIT;')
    call = "SELECT aos_capacity_publication_private.withdraw_origin(decode('%s','hex'),decode('%s','hex'));" % (raw.hex(),signature.hex())
    return dict(raw=raw,signature=signature,digest=hashlib.sha256(raw).hexdigest(),call=call,document=document,payload=payload)


def test_signed_origin_withdrawal_actual_commit_rollback_replay(committed_native_registry):
    f = committed_native_registry
    w = prepared_withdrawal(f)
    assert f['run'](f['begin']+w['call']+'ROLLBACK;').stdout.strip() == w['digest']
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin_withdrawal;').stdout.strip() == '0'
    assert f['run']('SELECT epoch FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '1'
    assert f['run'](f['begin']+w['call']+'COMMIT;').stdout.strip() == w['digest']
    assert f['run']("SELECT encode(raw_body,'hex'),encode(signature,'hex'),prior_epoch,new_epoch FROM aos_capacity_publication_private.origin_withdrawal;").stdout.strip() == '|'.join([w['raw'].hex(),w['signature'].hex(),'1','2'])
    assert f['run']('SELECT epoch,head_origin_hash IS NULL FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '2|t'
    assert f['run'](f['begin']+w['call']+'COMMIT;').stdout.strip() == w['digest']
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin_withdrawal;').stdout.strip() == '1'
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin; SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip().splitlines() == ['1','1']
    rejected = f['run'](f['begin']+w['document']['register']+'COMMIT;',success=False)
    assert 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' in rejected.stderr
    print('CAPACITY_SIGNED_WITHDRAWAL_COMMIT_PROOF '+f['database']+' rollback=epoch1 commit=epoch2 replay=single history=preserved source_grant=false')

    changed = json.loads(w['raw'])
    changed['assetId'] = 'another-valid-withdrawal'
    changed_raw = canonical_json(changed)
    changed_signature = f['sign_key'].sign(changed_raw)
    changed_call = "SELECT aos_capacity_publication_private.withdraw_origin(decode('%s','hex'),decode('%s','hex'));" % (changed_raw.hex(),changed_signature.hex())
    assert 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED' in f['run'](f['begin']+changed_call+'COMMIT;',success=False).stderr
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin_withdrawal; SELECT epoch FROM aos_capacity_publication_private.registry_epoch;').stdout.strip().splitlines() == ['1','2']
    archived = f['run']("SELECT encode(o.raw_body,'hex'),encode(o.signature,'hex'),encode(s.raw_body,'hex') FROM aos_capacity_publication_private.origin o JOIN aos_capacity_publication_private.root_snapshot s USING(org_id,project_id,snapshot_hash);").stdout.strip().split('|')
    original_register = "SELECT aos_capacity_publication_private.register_origin(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));" % tuple(archived)
    assert 'CAPACITY_ORIGIN_REGISTRATION_DENIED' in f['run'](f['begin']+original_register+'COMMIT;',success=False).stderr


@pytest.mark.parametrize('fault', ['signature','foreign_signer','publisher','key','subject','anchor','origin_hash',
    'origin_id','origin_revision','deployment','epoch','expired','future','purpose','extra','null','epoch_bool',
    'schema_bool','epoch_zero','epoch_overflow','origin_revision_bool','tenant','long_window','canary','session'])
def test_independent_signed_withdrawal_fault_retains_original_epoch(committed_native_registry, fault):
    f = committed_native_registry
    w = prepared_withdrawal(f, fault)
    begin = f['begin']
    if fault == 'canary': begin = begin.replace("aos.org_id='org-org'", "aos.org_id='dev-org'")
    if fault == 'session': begin = begin.replace('SET SESSION AUTHORIZATION aos_provider_capacity_policy_publisher;', '')
    failure = f['run'](begin+w['call']+'COMMIT;',success=False)
    malformed = fault in ('purpose','extra','null','epoch_bool','schema_bool','epoch_zero','epoch_overflow','origin_revision_bool','tenant','long_window')
    if malformed:
        from aos_api.aip_provider_capacity_withdrawal_contracts import ProviderCapacityOriginWithdrawal
        with pytest.raises(ValueError): ProviderCapacityOriginWithdrawal.model_validate(json.loads(w['raw']))
    expected = 'CAPACITY_ORIGIN_WITHDRAWAL_REQUIRED' if malformed else 'CAPACITY_ORIGIN_WITHDRAWAL_DENIED'
    assert expected in failure.stderr, failure.stderr
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin_withdrawal;').stdout.strip() == '0'
    assert f['run']('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '1|'+w['document']['origin_hash']
    assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip() == '1'
    print('CAPACITY_SIGNED_WITHDRAWAL_NEGATIVE_PROOF '+f['database']+' fault='+fault+' original_epoch=1 history=preserved')


def test_signed_withdrawal_acl_immutability_and_verifier_drift(committed_native_registry):
    f = committed_native_registry
    w = prepared_withdrawal(f)
    for role in ['aos_runtime','aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher']:
        assert f['run']("SELECT has_table_privilege('%s','aos_capacity_publication_private.origin_withdrawal','SELECT,INSERT,UPDATE,DELETE,TRUNCATE'),has_function_privilege('%s','aos_capacity_publication_private.read_origin_withdrawal(bytea)','EXECUTE');" % (role,role)).stdout.strip() == 'f|f'
        denied = f['run']('BEGIN; SET SESSION AUTHORIZATION '+role+'; SELECT * FROM aos_capacity_publication_private.origin_withdrawal; COMMIT;',success=False)
        assert 'permission denied' in denied.stderr
        if role != 'aos_provider_capacity_policy_publisher':
            denied = f['run']('BEGIN; SET SESSION AUTHORIZATION '+role+';'+w['call']+'COMMIT;',success=False)
            assert 'permission denied' in denied.stderr
    assert f['run']("SELECT relrowsecurity,relforcerowsecurity,relowner='aos_capacity_publication_owner'::regrole FROM pg_class WHERE oid='aos_capacity_publication_private.origin_withdrawal'::regclass;").stdout.strip() == 't|t|t'
    assert f['run']("SELECT prosecdef,proowner='aos_capacity_publication_owner'::regrole,proconfig FROM pg_proc WHERE oid='aos_capacity_publication_private.withdraw_origin(bytea,bytea)'::regprocedure;").stdout.strip() == 't|t|{search_path=pg_catalog}'
    failed = f['run']('BEGIN; ALTER FUNCTION aos_ed25519.verify(bytea,bytea,bytea) OWNER TO aos_app;'+f['begin'].removeprefix('BEGIN;')+w['call']+'COMMIT;',success=False)
    assert 'CAPACITY_ORIGIN_VERIFIER_REQUIRED' in failed.stderr
    assert f['run']('SELECT epoch FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '1'
    f['run'](f['begin']+w['call']+'COMMIT;')
    for mutation in ['UPDATE aos_capacity_publication_private.origin_withdrawal SET revision=revision;','DELETE FROM aos_capacity_publication_private.origin_withdrawal;']:
        failure = f['run']('BEGIN;'+mutation+'COMMIT;',success=False)
        assert 'CAPACITY_PUBLICATION_IMMUTABLE' in failure.stderr
    for org,count in [('org-org','1'),('dev-org','0')]:
        assert f['run']("BEGIN; SET LOCAL ROLE aos_capacity_publication_owner; SET LOCAL aos.org_id='%s'; SET LOCAL aos.project_id='dev-project'; SELECT count(*) FROM aos_capacity_publication_private.origin_withdrawal; ROLLBACK;" % org).stdout.strip() == count


@pytest.mark.parametrize('order', ['registrar_first','withdrawal_first'])
def test_document_registration_vs_signed_withdrawal_actual_commit(committed_native_registry, order):
    import time
    from tests.aip.test_capacity_publication_registry_pg import _NativeSqlSession
    f = committed_native_registry
    w = prepared_withdrawal(f)
    registrar,writer = _NativeSqlSession(f['command']),_NativeSqlSession(f['command'])
    try:
        registrar.send(f['begin']+'SELECT pg_backend_pid();')
        rpid = int(registrar.line())
        writer.send(f['begin']+'SELECT pg_backend_pid();')
        wpid = int(writer.line())
        if order == 'registrar_first':
            registrar.send(w['document']['register'])
            assert registrar.line() == w['document']['digest']
            writer.send(w['call'])
            holding,waiting = rpid,wpid
        else:
            writer.send(w['call'])
            assert writer.line() == w['digest']
            registrar.send(w['document']['register'])
            holding,waiting = wpid,rpid
        deadline = time.monotonic()+4
        blocked = False
        while time.monotonic()<deadline:
            if f['run']('SELECT %s=ANY(pg_blocking_pids(%s));' % (holding,waiting)).stdout.strip() == 't':
                blocked = True
                break
            time.sleep(.03)
        assert blocked
        if order == 'registrar_first':
            registrar.send("COMMIT; SELECT 'registrar-committed';")
            assert registrar.line() == 'registrar-committed'
            assert writer.line() == w['digest']
        writer.send("COMMIT; SELECT 'withdrawal-committed';")
        assert writer.line() == 'withdrawal-committed'
        if order == 'withdrawal_first':
            assert registrar.lines.get(timeout=12) is None
            assert registrar.process.wait(timeout=5) != 0
            assert 'CAPACITY_DOCUMENT_REGISTRATION_DENIED' in ''.join(registrar.errors)
        assert f['run']('SELECT epoch,head_origin_hash IS NULL FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '2|t'
        assert f['run']('SELECT count(*) FROM aos_capacity_publication_private.origin_withdrawal; SELECT count(*) FROM aos_capacity_publication_private.origin; SELECT count(*) FROM aos_capacity_publication_private.document;').stdout.strip().splitlines() == ['1','1','1']
        print('CAPACITY_SIGNED_WITHDRAWAL_EPOCH_PROOF '+f['database']+' order='+order+' blocked=true epoch=2 signed_authority=true history=preserved')
    finally:
        for session in (registrar,writer):
            try: session.send('ROLLBACK;')
            except (BrokenPipeError,ValueError): pass
        registrar.close()
        writer.close()


def test_current_signed_authority_can_withdraw_expired_bootstrap(committed_native_registry):
    import time
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacityOriginBootstrap
    f = committed_native_registry
    origin = json.loads(f['body'])
    origin['validUntil'] = (datetime.now(UTC)+timedelta(seconds=3)).isoformat()
    f['body'] = canonical_json(ProviderCapacityOriginBootstrap.model_validate(origin).model_dump(mode='json',by_alias=True))
    w = prepared_withdrawal(f)
    time.sleep(3.1)
    assert f['run']("SELECT clock_timestamp()>=aos_capacity_publication_private.read_signed_time(convert_from(raw_body,'UTF8')::jsonb->'validUntil') FROM aos_capacity_publication_private.origin;").stdout.strip() == 't'
    assert f['run'](f['begin']+w['call']+'COMMIT;').stdout.strip() == w['digest']
    assert f['run']('SELECT epoch FROM aos_capacity_publication_private.registry_epoch;').stdout.strip() == '2'
    print('CAPACITY_SIGNED_WITHDRAWAL_EXPIRED_ORIGIN_PROOF '+f['database']+' bootstrap_expired=true withdrawal_current=true committed=true')


def test_signed_withdrawal_full_revision_domain_actual_commit(committed_native_registry):
    import random
    from aos_api.aip_provider_capacity_withdrawal_contracts import ProviderCapacityOriginWithdrawal
    f = committed_native_registry
    w = prepared_withdrawal(f)
    payload = w['payload']
    rng = random.Random(154)
    payload['revision'] = int('9'+''.join(str(rng.randrange(10)) for _ in range(4299)))
    raw = canonical_json(ProviderCapacityOriginWithdrawal.model_validate(payload).model_dump(mode='json',by_alias=True))
    signature = f['sign_key'].sign(raw)
    call = "SELECT aos_capacity_publication_private.withdraw_origin(decode('%s','hex'),decode('%s','hex'));" % (raw.hex(),signature.hex())
    assert f['run'](f['begin']+call+'COMMIT;').stdout.strip() == hashlib.sha256(raw).hexdigest()
    assert f['run']("SELECT length(revision),encode(raw_body,'hex') FROM aos_capacity_publication_private.origin_withdrawal;").stdout.strip() == '4300|'+raw.hex()
    assert f['run'](f['begin']+call+'COMMIT;').stdout.strip() == hashlib.sha256(raw).hexdigest()
    print('CAPACITY_SIGNED_WITHDRAWAL_REVISION_PROOF '+f['database']+' digits=4300 raw=exact committed=true replay=single')
