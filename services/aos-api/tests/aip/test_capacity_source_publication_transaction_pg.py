"""Complete publication boundary work; this initial RED is not full-chain proof."""
import psycopg
import pytest

from tests.aip.test_provider_capacity_source_pg import (
    native_signed_source, approved_command, private_database, signed_capacity_documents,
    source_proposal, source_inputs, drafted,
)
from tests.aip.test_provider_capacity_request_pg import original_inputs, SCOPE


@pytest.fixture(autouse=True)
def registered_database_isolation(request, _isolated_postgres_database, monkeypatch):
    """Each signed registration owns a retained database, including parameters."""
    import os
    from tests.conftest import _isolated_postgres_database as database_fixture

    registered_cases = {
        'test_registered_origin_documents_and_original_private_approval_share_database',
        'test_registered_original_inputs_prepare_native_v2_before_signing',
        'test_complete_native_publication_requires_actual_caller_commit',
        'test_native_registered_signed_document_current_rows_require_exact_originals',
        'test_native_signed_supplier_combination_keeps_original_approved_terms',
        'test_native_signing_permit_binds_exact_policy_and_controlled_source_root',
        'test_native_current_signed_document_single_field_faults_restore_exact_originals',
        'test_native_current_signed_exact_scope_matrix_and_ordinary_role_denial',
        'test_native_current_signed_actual_withdrawal_commit_rollback_and_replay',
        'test_native_current_signed_withdrawal_serializable_epoch_competition',
    }
    if request.node.originalname not in registered_cases:
        yield
        return
    # Never reuse or erase another case's immutable registry domain. Reuse the
    # existing bootstrap/migration/restore implementation, with retention required.
    assert os.environ.get('AOS_TEST_RETAIN_DATABASE') == '1'
    assert os.environ.get('AOS_TEST_USE_SHARED_DATABASE') == '0'
    assert psycopg.conninfo.conninfo_to_dict(os.environ['AOS_DATABASE_URL'])['dbname'].startswith('aos_test_')
    from aos_api import tenant_catalog, data_os_store
    with monkeypatch.context() as local:
        # These bootstrap caches describe the parent database. Restore them
        # only after every dependent fixture and the child environment close.
        local.setattr(tenant_catalog, '_schema_ready', False)
        local.setattr(data_os_store, '_schema_ready', False)
        database = database_fixture.__wrapped__()
        try:
            next(database)
            yield
        finally:
            database.close()


def test_private_native_publication_rejects_missing_original_bytes(native_signed_source):
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs

    material, actual_command, _, _, config = native_signed_source
    command, policy, attestation = actual_command()
    with connect_capacity_issuer(config, SCOPE) as conn:
        assert conn.pgconn.used_password is True
        checked = check_native_capacity_supplier_inputs(
            conn, command, policy, attestation, trust_roots=material['provider'])
        assert checked.authorization == 'SUPPLIER_DOCUMENT_SIGNATURES_ONLY_NO_CAPACITY_NO_START'
        before = conn.execute('SELECT count(*) AS n FROM public.aip_action_approval_event').fetchone()['n']
        conn.execute('SAVEPOINT incomplete_publication')
        try:
            conn.execute(
                'SELECT public.prepare_capacity_source(%s::bytea,%s::text,%s::text,%s::jsonb)',
                (b'{}', 'missing-original-publication', 'missing-original-source', '{}'))
        except psycopg.Error as error:
            sqlstate = error.sqlstate
        else:
            sqlstate = None
        finally:
            conn.execute('ROLLBACK TO SAVEPOINT incomplete_publication')
            conn.execute('RELEASE SAVEPOINT incomplete_publication')
        assert conn.execute('SELECT count(*) AS n FROM public.aip_action_approval_event').fetchone()['n'] == before
        assert sqlstate == '22023', (
            'prepare must validate missing original bytes; undefined42883 is missing implementation, '
            f'not complete publication refusal; observed SQLSTATE={sqlstate}')


def test_native_verifier_and_private_scram_share_one_isolated_database(native_signed_source):
    """Prerequisite only: this does not register trust or issue any Source."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs

    material, actual_command, _, _, config = native_signed_source
    command, policy, attestation = actual_command()
    key = Ed25519PrivateKey.generate()
    raw = b'isolated-crypto-scram-prerequisite-no-capacity'
    signature = key.sign(raw)
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    with isolated_owner() as owner:
        assert owner.execute('SELECT current_database() AS db').fetchone()['db'] == config.database
        catalog = owner.execute("SELECT p.prosecdef,p.proisstrict,p.provolatile,r.rolname,r.rolcanlogin "
            "FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner "
            "WHERE p.oid='aos_ed25519.verify(bytea,bytea,bytea)'::regprocedure").fetchone()
        assert catalog == dict(prosecdef=False, proisstrict=True, provolatile='i',
                               rolname='aos_ed25519_owner', rolcanlogin=False)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute('SELECT aos_ed25519.verify(%s,%s,%s) AS valid',
            (signature, raw, public)).fetchone()['valid'] is True
        assert owner.execute('SELECT aos_ed25519.verify(%s,%s,%s) AS valid',
            (signature, raw+b'altered', public)).fetchone()['valid'] is False
    with connect_capacity_issuer(config, SCOPE) as conn:
        assert conn.pgconn.used_password is True
        assert conn.execute('SELECT current_database() AS db').fetchone()['db'] == config.database
        checked = check_native_capacity_supplier_inputs(conn,command,policy,attestation,
            trust_roots=material['provider'])
        assert checked.execution_allowed is False
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute('SELECT aos_ed25519.verify(%s,%s,%s)',(signature, raw, public))


def test_publication_owner_reads_original_approved_rows_without_mutation(native_signed_source):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_formal_boundary import LOCKS, TABLES
    from aos_api.aip_provider_capacity_publication_transaction import POLICY_TABLES
    from aos_api.aip_provider_capacity_publication_transaction import require_original_fact_boundary
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_APPROVED_SOURCE_ROW_SQL, CAPACITY_APPROVED_ALLOCATION_ROW_SQL)
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate, ProviderCapacityBasisCandidate

    material, actual_command, _, source, _ = native_signed_source
    command, _, _ = actual_command()
    params=dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id,maker=material['maker'],
        proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
        proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
        approval_event_hash=command.approval_event.content_hash)
    with isolated_owner() as owner:
        require_original_fact_boundary(owner)
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        row=owner.execute(CAPACITY_APPROVED_SOURCE_ROW_SQL,params).fetchone()
        assert row is not None and row['created_by']==material['maker']
        assert row['proposal_hash']==command.approved_proposal.content_hash
        allocation=owner.execute(CAPACITY_APPROVED_ALLOCATION_ROW_SQL,dict(
            org_id=SCOPE.org_id,project_id=SCOPE.project_id,maker=material['maker'],
            approval_event_id=source.allocation_approval_ref.asset_id,
            approval_event_hash=source.allocation_approval_ref.content_hash,
            request_id=source.allocation_request_ref.asset_id,
            request_hash=source.allocation_request_ref.content_hash)).fetchone()
        assert allocation is not None and allocation['action_type_id']=='aip_request_provider_capacity'
        account=ProviderCapacitySourceActionGuard._candidate(owner,SCOPE,source.physical_account_ref,
            'account',ProviderPhysicalAccountCandidate,material['maker'])
        basis=ProviderCapacitySourceActionGuard._candidate(owner,SCOPE,source.basis_ref,
            'basis',ProviderCapacityBasisCandidate,material['maker'])
        assert basis.physical_account_ref==source.physical_account_ref
        assert account.supplier_id==material['policy']['supplierId']
        assert owner.execute('SELECT count(*) AS n FROM public.aip_action_approval_event WHERE proposal_id=ANY(%s)',
            ([row['proposal_id'],allocation['proposal_id']],)).fetchone()['n']==2
        for table,column in LOCKS.items():
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with owner.transaction():
                    owner.execute(f'UPDATE public.{table} SET {column}={column}')
        owner.execute("SELECT set_config('aos.org_id','dev-org',true)")
        for table in POLICY_TABLES:
            assert owner.execute(f'SELECT count(*) AS n FROM public.{table}').fetchone()['n']==0
    with isolated_owner() as owner:
        grants=owner.execute("SELECT c.relname,a.privilege_type FROM pg_class c,LATERAL aclexplode(c.relacl) a "
            "WHERE c.relnamespace='public'::regnamespace AND a.grantee='aos_capacity_publication_owner'::regrole").fetchall()
        assert {(r['relname'],r['privilege_type']) for r in grants}=={(t,'SELECT') for t in TABLES}


@pytest.mark.parametrize('fault',['extra_select','public_select','extra_column','public_column',
    'login','membership','default_acl','schema_create','database_create','policy','extra_policy','rls','disabled_trigger','guard_body','guard_public_execute'])
def test_original_fact_owner_boundary_rejects_effective_drift(native_signed_source,fault):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_transaction import (
        require_original_fact_boundary, CapacityPublicationBoundaryBlocked, GUARD_NAME)
    statements={
        'extra_select':'GRANT SELECT ON public.twa_org TO aos_capacity_publication_owner',
        'public_select':'GRANT SELECT ON public.twa_org TO PUBLIC',
        'extra_column':'GRANT UPDATE(name) ON public.meta_object_type TO aos_capacity_publication_owner',
        'public_column':'GRANT UPDATE(name) ON public.meta_object_type TO PUBLIC',
        'login':'ALTER ROLE aos_capacity_publication_owner LOGIN',
        'membership':'GRANT aos_runtime TO aos_capacity_publication_owner',
        'default_acl':'ALTER DEFAULT PRIVILEGES FOR ROLE aos_capacity_publication_owner GRANT SELECT ON TABLES TO aos_runtime',
        'schema_create':'GRANT CREATE ON SCHEMA public TO aos_capacity_publication_owner',
        'database_create':None,
        'policy':'ALTER POLICY capacity_publication_fact_restrict_a0v155 ON public.aip_action_proposal USING(true)',
        'extra_policy':'CREATE POLICY extra_publication_owner ON public.aip_action_proposal TO aos_capacity_publication_owner USING(true)',
        'rls':'ALTER TABLE public.aip_action_proposal NO FORCE ROW LEVEL SECURITY',
        'disabled_trigger':f'ALTER TABLE public.aip_action_proposal DISABLE TRIGGER {GUARD_NAME}',
        'guard_body':f'CREATE OR REPLACE FUNCTION public.{GUARD_NAME}() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$',
        'guard_public_execute':f'GRANT EXECUTE ON FUNCTION public.{GUARD_NAME}() TO PUBLIC',
    }
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_original_fact_boundary(owner)
        owner.execute('SAVEPOINT original_fact_native_fault')
        try:
            if fault=='database_create':
                from psycopg import sql
                owner.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO aos_capacity_publication_owner').format(sql.Identifier(owner.info.dbname)))
            else:
                owner.execute(statements[fault])
            with pytest.raises(CapacityPublicationBoundaryBlocked):
                require_original_fact_boundary(owner)
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            with pytest.raises(psycopg.errors.InvalidParameterValue) as captured:
                with owner.transaction():
                    owner.execute('SELECT aos_capacity_publication_private.require_original_fact_boundary()')
            assert captured.value.diag.message_primary=='CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED'
            _assert_native_withdrawal_rejects(owner,'WITHDRAWAL_PUBLICATION_CALLER_DRIFT')
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT original_fact_native_fault')
        require_original_fact_boundary(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        owner.rollback()


def test_registered_origin_documents_and_original_private_approval_share_database(native_signed_source,tmp_path):
    material = _registered_publication_inputs(native_signed_source,tmp_path)
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    command, policy, attestation = material['actual_command']()
    with connect_capacity_issuer(material['config'],SCOPE) as conn:
        assert conn.pgconn.used_password is True
        checked=check_native_capacity_supplier_inputs(conn,command,policy,attestation,
            trust_roots=material['provider'])
        assert checked.execution_allowed is False
        assert checked.source_policy_hash==material['refs'][0]['contentHash']
        assert checked.supplier_attestation_hash==material['refs'][1]['contentHash']
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        fence=owner.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchone()
        assert fence==dict(epoch=1,head_origin_hash=material['origin_hash'])
        rows=owner.execute('SELECT kind,asset_id,revision,content_hash,raw_body,signature,origin_hash,origin_epoch,snapshot_hash FROM aos_capacity_publication_private.document ORDER BY kind').fetchall()
        assert len(rows)==3
        by_kind={r['kind']:r for r in rows}
        for ref,(body,signature) in zip(material['refs'],material['documents']):
            row=by_kind[ref['assetType']]
            assert (row['asset_id'],row['revision'],row['content_hash'])==(ref['assetId'],str(ref['revision']),ref['contentHash'])
            assert (bytes(row['raw_body']),bytes(row['signature']))==(body,signature)
            assert (row['origin_hash'],row['origin_epoch'],row['snapshot_hash'])==(material['origin_hash'],1,material['snapshot_hash'])
        import base64,json
        permit_body=json.loads(material['documents'][2][0])
        root=owner.execute('SELECT public_key,root_revision FROM aos_capacity_publication_private.root_entry '
            'WHERE snapshot_hash=%s AND publisher_codepoints=%s::integer[] AND key_id_codepoints=%s::integer[]',
            (material['snapshot_hash'],[ord(c) for c in permit_body['signerPublisher']],
             [ord(c) for c in permit_body['signerKeyId']])).fetchone()
        assert root is not None
        assert bytes(root['public_key'])==base64.b64decode(permit_body['signerPublicKey'],validate=True)
        assert root['root_revision']==permit_body['signerRootRevision']
        assert permit_body['sourcePolicyRef']==material['refs'][0]
    print('CAPACITY_COMBINED_ORIGINAL_INPUT_PROOF same_database=true native_scram=true original_approvals=true signed_origin=true registered_exact_documents=3 source_published=false')


def _registered_publication_inputs(native_signed_source,tmp_path,*,signed_fault=None,permit_fault=None,source_root_fault=None):
    """Real original inputs plus controlled test bootstrap; never formal authority."""
    import base64
    import hashlib
    import json
    from uuid import uuid4
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_provider_capacity_publication_contracts import (
        ProviderCapacitySigningPermit,ProviderCapacityOriginBootstrap,
        freeze_capacity_trust_root_snapshot)
    from tests.aip.test_provider_capacity_publication_pg import permit,bootstrap
    from tests.aip._runtime_guard_history_fixture import isolated_owner

    f,actual_command,_,_,config=native_signed_source
    with isolated_owner() as owner:
        probe=owner.execute('SELECT oid,(SELECT system_identifier::text FROM pg_control_system()) AS cluster FROM pg_database WHERE datname=current_database()').fetchone()
        assert owner.info.dbname==config.database
    target=dict(host=config.host,port=config.port,database=config.database,databaseOid=probe['oid'],
        clusterIdentifier=probe['cluster'],issuerRole='aos_provider_capacity_issuer')
    f['policy']['deploymentTarget']=target
    if signed_fault is not None:
        signed_fault(f)  # Own test documents, before genuine signing/registration.
    source_key=Ed25519PrivateKey.generate()
    source_public=source_key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    source_root=dict(f['roots'][0],publisher='isolated-source-signer',keyId='isolated-source-key',
        publicKey=base64.b64encode(source_public).decode())
    if source_root_fault is not None:
        source_root_fault(source_root)  # Separate controlled signing root, before snapshot.
    f['roots'].append(source_root)
    f['rootfile'].write_text(json.dumps(dict(trustRoots=f['roots'])))
    transport=freeze_capacity_trust_root_snapshot(f['provider'])
    command,policy,attestation=actual_command()
    raw_permit=permit()
    raw_permit.update(assetId='integrated-permit-'+uuid4().hex,publisher=policy.payload.publisher,
        keyId=policy.payload.key_id,deploymentTarget=target,
        sourcePolicyRef=command.source_policy_ref.model_dump(mode='json',by_alias=True),
        signerPublisher=source_root['publisher'],signerKeyId=source_root['keyId'],
        signerRootRevision=source_root['revision'],signerPublicKey=source_root['publicKey'])
    if permit_fault is not None:
        permit_fault(raw_permit)  # Own permit, before genuine signing/registration.
    parsed_permit=ProviderCapacitySigningPermit.model_validate(raw_permit)
    permit_bytes=canonical_json(parsed_permit.model_dump(mode='json',by_alias=True))
    permit_signature=f['keys'][policy.payload.publisher].sign(permit_bytes)
    documents=[(canonical_json(doc.payload.model_dump(mode='json',by_alias=True)),
        base64.b64decode(doc.signature,validate=True)) for doc in (policy,attestation)]
    documents.append((permit_bytes,permit_signature))
    refs=[command.source_policy_ref.model_dump(mode='json',by_alias=True),
          command.supplier_attestation_ref.model_dump(mode='json',by_alias=True),
          dict(assetType='ProviderCapacitySigningPermitRevision',assetId=parsed_permit.asset_id,
               revision=parsed_permit.revision,contentHash=hashlib.sha256(permit_bytes).hexdigest())]
    anchor_key=Ed25519PrivateKey.generate()
    anchor_public=anchor_key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    raw_origin=bootstrap()
    raw_origin.update(assetId='integrated-origin-'+uuid4().hex,bootstrapId='integrated-bootstrap-'+uuid4().hex,
        publisher='isolated-controlled-anchor',keyId='isolated-anchor-key',publisherSubject='isolated-publisher-subject',
        deploymentTarget=target,rootSnapshotHash=transport.content_hash,allowedDocumentRefs=refs)
    origin=ProviderCapacityOriginBootstrap.model_validate(raw_origin)
    origin_bytes=canonical_json(origin.model_dump(mode='json',by_alias=True))
    origin_hash=hashlib.sha256(origin_bytes).hexdigest()
    with isolated_owner() as owner:
        assert owner.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.registry_epoch').fetchone()['n']==0
        owner.execute('INSERT INTO aos_capacity_publication_private.deployment_anchor '
            '(org_id,project_id,anchor_revision,signer_publisher,signer_key_id,signer_public_key,publisher_subject,deployment_target) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',
            (*SCOPE.key,origin.anchor_revision,origin.publisher,origin.key_id,anchor_public,
             origin.publisher_subject,json.dumps(target)))
        owner.execute('INSERT INTO aos_capacity_publication_private.registry_epoch(org_id,project_id,anchor_revision) VALUES(%s,%s,%s)',
            (*SCOPE.key,origin.anchor_revision))
    # Existing signed registration path only. Controlled publisher session in
    # this test is not a claim of formal publisher login/identity acceptance.
    with isolated_owner() as publisher:
        publisher.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        publisher.execute('SET SESSION AUTHORIZATION aos_provider_capacity_policy_publisher')
        assert publisher.execute('SELECT aos_capacity_publication_private.register_origin(%s,%s,%s) AS hash',
            (origin_bytes,anchor_key.sign(origin_bytes),transport.canonical_bytes)).fetchone()['hash']==origin_hash
        for ref,(raw,signature) in zip(refs,documents):
            assert publisher.execute('SELECT aos_capacity_publication_private.register_document(%s,%s,%s) AS hash',
                (ref['assetType'],raw,signature)).fetchone()['hash']==ref['contentHash']
        publisher.execute('RESET SESSION AUTHORIZATION')
    return dict(actual_command=actual_command,config=config,provider=f['provider'],refs=refs,documents=documents,
        origin_hash=origin_hash,snapshot_hash=transport.content_hash,source_key=source_key,anchor_key=anchor_key,origin_payload=origin.model_dump(mode='json',by_alias=True))


def test_registered_original_inputs_prepare_native_v2_before_signing(native_signed_source,tmp_path):
    """Preparation dependency only; full sign/COMMIT/consumer still required."""
    import json
    from uuid import uuid4
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command,capacity_source_preparation_bytes
    from aos_api.aip_provider_capacity_source_contracts import capacity_issuance_binding
    from aos_api.aip_provider_capacity_publication_contracts import (
        PublishedProviderCapacitySourceV2,parse_signed_capacity_body)
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    material=_registered_publication_inputs(native_signed_source,tmp_path)
    command,_,_=material['actual_command']()
    principal=authenticate_capacity_issuance_command(command)
    request_hash=capacity_issuance_binding(SCOPE,principal.subject,command).content_hash
    raw=capacity_source_preparation_bytes(command)
    # No JWT/secret reaches SQL, including hidden SecretStr placeholders.
    assert b'bearerToken' not in raw and b'bearer_token' not in raw
    asset_id='native-source-'+uuid4().hex
    with connect_capacity_issuer(material['config'],SCOPE) as conn:
        assert conn.pgconn.used_password is True
        native=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        row=conn.execute('SELECT * FROM public.prepare_capacity_source(%s::bytea,%s::text,%s::text,%s::jsonb)',
            (raw,command.idempotency_key,asset_id,json.dumps(material['refs'][-1]))).fetchone()
        prepared=parse_signed_capacity_body(bytes(row['source_raw']),PublishedProviderCapacitySourceV2)
        assert prepared.asset_id==asset_id and prepared.request_hash==request_hash
        assert prepared.issuance_context.maker_subject==principal.subject
        assert prepared.issuance_context.transaction_id==native['xid']
        assert prepared.issuance_context.backend_pid==native['pid']
        assert prepared.execution_allowed is False
        conn.rollback()  # Pending prepare is never committed as a Source.


@pytest.mark.parametrize('outcome',['committed','invalid_signature','unfinished'])
def test_complete_native_publication_requires_actual_caller_commit(native_signed_source,tmp_path,outcome):
    """Real transaction contract; fixture signing alone is not signer acceptance."""
    import hashlib,json
    from uuid import uuid4
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_source_issuer import (
        authenticate_capacity_issuance_command,capacity_source_preparation_bytes)
    from aos_api.aip_provider_capacity_source_contracts import capacity_issuance_binding
    from aos_api.aip_provider_capacity_publication_contracts import (
        PublishedProviderCapacitySourceV2,parse_signed_capacity_body)
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer

    material=_registered_publication_inputs(native_signed_source,tmp_path)
    command,_,_=material['actual_command']()
    principal=authenticate_capacity_issuance_command(command)
    request_hash=capacity_issuance_binding(SCOPE,principal.subject,command).content_hash
    command_raw=capacity_source_preparation_bytes(command)
    assert command.bearer_token.get_secret_value().encode() not in command_raw
    asset_id='native-commit-'+uuid4().hex
    with connect_capacity_issuer(material['config'],SCOPE) as conn:
        assert conn.pgconn.used_password is True
        native=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        prepared_row=conn.execute('SELECT * FROM public.prepare_capacity_source(%s::bytea,%s::text,%s::text,%s::jsonb)',
            (command_raw,command.idempotency_key,asset_id,json.dumps(material['refs'][-1]))).fetchone()
        raw=bytes(prepared_row['source_raw'])
        parsed=parse_signed_capacity_body(raw,PublishedProviderCapacitySourceV2)
        assert parsed.asset_id==asset_id and parsed.request_hash==request_hash
        assert parsed.issuance_context.maker_subject==principal.subject
        assert parsed.issuance_context.transaction_id==native['xid']
        assert parsed.issuance_context.backend_pid==native['pid']
        assert parsed.execution_allowed is False
        signature=material['source_key'].sign(raw)
        if outcome=='unfinished':
            # Invoke real caller COMMIT, not SET CONSTRAINTS or a fake trigger.
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.commit()
            conn.rollback()
        elif outcome=='invalid_signature':
            changed=bytes([signature[0]^1])+signature[1:]
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('SELECT * FROM public.commit_capacity_source(%s::text,%s::bytea,%s::bytea)',
                    (command.idempotency_key,raw,changed))
            conn.rollback()
        else:
            committed=conn.execute('SELECT * FROM public.commit_capacity_source(%s::text,%s::bytea,%s::bytea)',
                (command.idempotency_key,raw,signature)).fetchone()
            assert committed['asset_id']==asset_id and committed['revision']==1
            assert committed['content_hash']==hashlib.sha256(raw).hexdigest()
            assert bytes(committed['source_raw'])==raw
            assert bytes(committed['signature'])==signature
            conn.commit()
    # A distinct actual connection observes durable outcome. Test admin reads
    # evidence only; issuer never gets a private table grant or direct insert.
    with isolated_owner() as owner:
        owner.read_only=True
        row=owner.execute('SELECT asset_id,revision,content_hash,source_raw,signature FROM '
            'aos_capacity_publication_private.source_publication WHERE org_id=%s AND project_id=%s AND asset_id=%s',
            (*SCOPE.key,asset_id)).fetchone()
        if outcome=='committed':
            assert row is not None and row['revision']==1
            assert row['content_hash']==hashlib.sha256(raw).hexdigest()
            assert bytes(row['source_raw'])==raw and bytes(row['signature'])==signature
            durable=parse_signed_capacity_body(bytes(row['source_raw']),PublishedProviderCapacitySourceV2)
            assert durable.issuance_context==parsed.issuance_context
            assert durable.execution_allowed is False
        else:
            assert row is None


def test_preparation_transport_uses_verified_authentication_without_sql_secret(native_signed_source):
    from datetime import UTC,datetime
    import json,os
    from aos_api.oidc import verify_access_token
    from aos_api.aip_provider_capacity_source_issuer import capacity_source_preparation_bytes,authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_source_contracts import capacity_issuance_binding
    _,actual_command,_,_,_=native_signed_source
    command,_,_=actual_command()
    principal=authenticate_capacity_issuance_command(command)
    verified=verify_access_token(command.bearer_token.get_secret_value())
    raw=capacity_source_preparation_bytes(command)
    payload=json.loads(raw)
    assert payload['makerSubject']==principal.subject
    assert payload['requestHash']==capacity_issuance_binding(SCOPE,principal.subject,command).content_hash
    assert payload['authentication']==dict(makerSubject=principal.subject,oidcIssuer=verified['iss'],
        oidcAudience=os.environ['AOS_OIDC_AUDIENCE'],
        authenticationExpiresAt=datetime.fromtimestamp(verified['exp'],UTC).isoformat().replace('+00:00','Z'))
    assert payload['command']==command.model_dump(mode='json',by_alias=True,exclude={'bearer_token','idempotency_key'})
    assert command.bearer_token.get_secret_value().encode() not in raw
    assert set(payload)=={'protocol','makerSubject','requestHash','command','authentication'}
    assert b'bearerToken' not in raw and b'bearer_token' not in raw


def test_preparation_transport_rejects_actual_signature_drift(native_signed_source):
    from pydantic import SecretStr
    from aos_api.aip_provider_capacity_source_issuer import capacity_source_preparation_bytes,ProviderCapacityIssuanceBlocked
    _,actual_command,_,_,_=native_signed_source
    command,_,_=actual_command()
    parts=command.bearer_token.get_secret_value().split('.')
    parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
    invalid=command.model_copy(update={'bearer_token':SecretStr('.'.join(parts))})
    with pytest.raises(ProviderCapacityIssuanceBlocked,match='CAPACITY_SOURCE_PREPARATION_AUTHENTICATION_REQUIRED') as caught:
        capacity_source_preparation_bytes(invalid)
    assert invalid.bearer_token.get_secret_value() not in str(caught.value)


@pytest.mark.parametrize('kind',['source','allocation'])
@pytest.mark.parametrize('fault',['action_metadata','object_metadata','maker_role','checker_role','draft_payload','draft_status','policy','eligibility'])
def test_original_approval_sql_rechecks_native_approval_facts_without_client_guard(native_signed_source,kind,fault):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVED_SOURCE_ROW_SQL,CAPACITY_APPROVED_ALLOCATION_ROW_SQL
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    _,actual_command,_,source,_=native_signed_source
    command,_,_=actual_command()
    maker=authenticate_capacity_issuance_command(command).subject
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,maker=maker)
    if kind=='source':
        statement=CAPACITY_APPROVED_SOURCE_ROW_SQL
        params.update(proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
            proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
            approval_event_hash=command.approval_event.content_hash)
        action='aip_review_provider_capacity_source'
    else:
        statement=CAPACITY_APPROVED_ALLOCATION_ROW_SQL
        params.update(request_id=source.allocation_request_ref.asset_id,request_hash=source.allocation_request_ref.content_hash,
            approval_event_id=source.allocation_approval_ref.asset_id,approval_event_hash=source.allocation_approval_ref.content_hash)
        action='aip_request_provider_capacity'
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        original=owner.execute(statement,params).fetchone()
        assert original is not None
        owner.execute('RESET ROLE')
        original_event_hash=params['approval_event_hash']
        owner.execute('SAVEPOINT metadata_drift')
        try:
            if fault=='action_metadata':
                owner.execute('UPDATE public.meta_action_type SET name=%s WHERE id=%s',('native metadata drift',action))
            elif fault=='object_metadata':
                object_id='ProviderCapacitySourceReview' if kind=='source' else 'ProviderCapacityRequest'
                owner.execute('UPDATE public.meta_object_type SET name=%s WHERE id=%s',('native object drift',object_id))
            elif fault in {'maker_role','checker_role'}:
                subject=maker if fault=='maker_role' else owner.execute(
                    'SELECT actor_id FROM public.aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
                    (*SCOPE.key,params['approval_event_id'])).fetchone()['actor_id']
                owner.execute('UPDATE public.meta_membership SET role=%s WHERE org_id=%s AND project_id=%s AND subject=%s',
                    ('developer',*SCOPE.key,subject))
            else:
                # Test-admin-only historical fact corruption in a savepoint;
                # never manufacture an approval or bypass a formal issuer.
                owner.execute("SET LOCAL session_replication_role='replica'")
                if fault=='draft_payload':
                    owner.execute("UPDATE public.aip_action_draft SET snapshot=jsonb_set(snapshot,'{payload}','{}'::jsonb) WHERE org_id=%s AND project_id=%s AND proposal_id=%s",(*SCOPE.key,original['proposal_id']))
                elif fault=='draft_status':
                    owner.execute("UPDATE public.aip_action_draft SET status='awaiting_approval' WHERE org_id=%s AND project_id=%s AND proposal_id=%s",(*SCOPE.key,original['proposal_id']))
                elif fault=='policy':
                    owner.execute("UPDATE public.aip_action_proposal SET policy_snapshot=policy_snapshot||'{\"verified\":true}'::jsonb WHERE org_id=%s AND project_id=%s AND proposal_id=%s",(*SCOPE.key,original['proposal_id']))
                else:
                    owner.execute('UPDATE public.aip_action_approval_event SET eligibility_snapshot_hash=%s WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',('c'*64,*SCOPE.key,params['approval_event_id']))
                owner.execute("SET LOCAL session_replication_role='origin'")
                if fault=='eligibility':
                    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVAL_EVENT_PROJECTION_SQL
                    # Keep the actual altered event exact-ref coherent so the
                    # native original eligibility predicate is what rejects it.
                    params['approval_event_hash']=owner.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,params).fetchone()['hash']
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert owner.execute(statement,params).fetchone() is None, 'Native original facts cannot depend on later client Guard'
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT metadata_drift')
            params['approval_event_hash']=original_event_hash
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(statement,params).fetchone() is not None


def test_native_allocation_binding_rejects_coherent_wrong_hash(native_signed_source):
    """Matching hashes do not replace the original three-field calculation."""
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_APPROVED_ALLOCATION_ROW_SQL,CAPACITY_APPROVAL_EVENT_PROJECTION_SQL)
    _,actual_command,_,source,_=native_signed_source
    command,_,_=actual_command()
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
        maker=authenticate_capacity_issuance_command(command).subject,
        request_id=source.allocation_request_ref.asset_id,
        request_hash=source.allocation_request_ref.content_hash,
        approval_event_id=source.allocation_approval_ref.asset_id,
        approval_event_hash=source.allocation_approval_ref.content_hash)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        original=owner.execute(CAPACITY_APPROVED_ALLOCATION_ROW_SQL,params).fetchone()
        assert original is not None
        expected=canonical_hash(dict(requestId=params['request_id'],requestHash=params['request_hash'],
            actionTypeRevisionHash=original['action_type_snapshot']['revisionHash']))
        assert original['action_binding_hash']==expected
        owner.execute('RESET ROLE')
        original_event_hash=params['approval_event_hash']
        owner.execute('SAVEPOINT coherent_binding_fault')
        try:
            snapshot=owner.execute('SELECT snapshot FROM public.aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (*SCOPE.key,original['proposal_id'])).fetchone()['snapshot']
            wrong='a'*64 if expected!='a'*64 else 'b'*64
            snapshot['actionBindingHash']=wrong
            changed_proposal_hash=canonical_hash(snapshot)
            # Isolated test-admin historical corruption only, rolled back.
            # Every dependent stored hash is updated to stay coherent.
            owner.execute("SET LOCAL session_replication_role='replica'")
            owner.execute('UPDATE public.aip_action_draft SET snapshot=%s WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (Jsonb(snapshot),*SCOPE.key,original['proposal_id']))
            owner.execute('UPDATE public.aip_action_proposal SET action_binding_hash=%s,proposal_hash=%s '
                'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (wrong,changed_proposal_hash,*SCOPE.key,original['proposal_id']))
            owner.execute('UPDATE public.aip_action_approval_event SET action_binding_hash=%s,proposal_hash=%s '
                'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
                (wrong,changed_proposal_hash,*SCOPE.key,params['approval_event_id']))
            owner.execute("SET LOCAL session_replication_role='origin'")
            params['approval_event_hash']=owner.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,params).fetchone()['hash']
            assert params['approval_event_hash']!=original_event_hash
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert owner.execute(CAPACITY_APPROVED_ALLOCATION_ROW_SQL,params).fetchone() is None, (
                'Native allocation must recompute original binding even when all stored hashes agree')
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT coherent_binding_fault')
            params['approval_event_hash']=original_event_hash
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(CAPACITY_APPROVED_ALLOCATION_ROW_SQL,params).fetchone() is not None


@pytest.mark.parametrize('identifier_prefix',['申请-中文-🧭','request-\'"\\-escape','e\u0301-组合-ß'])
def test_native_allocation_binding_preserves_original_unicode_acceptance(native_signed_source,approved_command,identifier_prefix):
    from uuid import uuid4
    from aos_api.db import connect_serializable
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_action import (
        propose_provider_capacity_request,decide_provider_capacity_request)
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVED_ALLOCATION_ROW_SQL
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,checker=approved_command[:2]
    source=native_signed_source[3]
    request_id=identifier_prefix+'-'+uuid4().hex
    # Use the actual original runtime INSERT right and immutable application's
    # checks; only the new request identifier/idempotency key differ.
    with connect_serializable(SCOPE) as runtime:
        row=runtime.execute('INSERT INTO public.aip_provider_capacity_request '
            '(org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at,created_at) '
            'SELECT org_id,project_id,%s,%s,request_hash,request_json,created_by,expires_at,created_at '
            'FROM public.aip_provider_capacity_request WHERE org_id=%s AND project_id=%s AND request_id=%s '
            'RETURNING request_hash,expires_at',
            (request_id,'unicode-request-'+uuid4().hex,*SCOPE.key,source.allocation_request_ref.asset_id)).fetchone()
        assert row is not None
        runtime.commit()
    proposal=propose_provider_capacity_request(maker,request_id,'unicode-proposal-'+uuid4().hex,row['expires_at'])
    approved=decide_provider_capacity_request(checker,proposal.proposal.id,'unicode-checker-'+uuid4().hex,
        DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
            expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',
            reason='original unicode binding acceptance',approvalExpiresAt=row['expires_at']))
    assert approved.proposal.status.value=='approved'
    event=approved.approvals[0]
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,maker=maker.subject,
        request_id=request_id,request_hash=row['request_hash'],approval_event_id=event.id,
        approval_event_hash=canonical_hash(event.model_dump(mode='json',by_alias=True)))
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        matched=owner.execute(CAPACITY_APPROVED_ALLOCATION_ROW_SQL,params).fetchone()
        assert matched is not None
        assert matched['action_binding_hash']==canonical_hash(dict(requestId=request_id,
            requestHash=row['request_hash'],actionTypeRevisionHash=matched['action_type_snapshot']['revisionHash']))


@pytest.mark.parametrize('representation',['nested_alias','offset_space','epoch_string'])
def test_original_source_binding_uses_typed_normalization_in_private_reader(native_signed_source,approved_command,representation,capsys):
    """Original stored representation may differ from its approved typed hash."""
    from datetime import timedelta,timezone
    from uuid import uuid4
    from aos_api.db import connect_serializable
    from aos_api.aip_action_store import AipActionStore,canonical_hash
    from aos_api.aip_action_models import CreateActionProposalRequest,DecideActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_provider_capacity_source_action import (
        ProviderCapacitySourceActionGuard,decide_provider_capacity_source)
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourceCandidate
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_APPROVED_SOURCE_ROW_SQL
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,checker=approved_command[:2]
    source=native_signed_source[3]
    raw=source.model_dump(mode='json',by_alias=True)
    if representation=='nested_alias':
        mapping=dict(assetType='asset_type',assetId='asset_id',contentHash='content_hash')
        raw['physicalAccountRef']={mapping.get(k,k):v for k,v in raw['physicalAccountRef'].items()}
    elif representation=='offset_space':
        zone=timezone(timedelta(hours=8))
        raw['validFrom']=source.valid_from.astimezone(zone).isoformat(sep=' ')
        raw['validUntil']=source.valid_until.astimezone(zone).isoformat(sep=' ')
    else:
        raw['validUntil']=str(int(source.valid_until.timestamp()))
    normalized=ProviderCapacitySourceCandidate.model_validate(raw)
    assert raw!=normalized.model_dump(mode='json',by_alias=True)
    guard=ProviderCapacitySourceActionGuard()
    with connect_serializable(SCOPE) as runtime:
        snapshot=guard.read_metadata(runtime)
    payload=dict(sourceCandidate=raw)
    body=CreateActionProposalRequest(actionTypeId=guard.action_id,purpose='capacity-source-review',
        payload=payload,expiresAt=normalized.valid_until)
    # Real original store/Guard and independent original decision, never
    # direct proposal/event INSERT or altered hashes of a fake approval.
    proposal=AipActionStore(provider_capacity_source_guard=guard).create_proposal(
        SCOPE,maker.subject,'source-domain-proposal-'+uuid4().hex,body,snapshot,
        classify_action_risk(guard.action_id,snapshot,payload,None))
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'source-domain-checker-'+uuid4().hex,
        DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
            expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',
            reason='original Source normalization acceptance',approvalExpiresAt=normalized.valid_until))
    assert approved.proposal.status.value=='approved'
    assert approved.proposal.payload['sourceCandidate']==raw
    typed_binding=canonical_hash(dict(sourceCandidate=normalized.model_dump(mode='json',by_alias=True),
        actionTypeRevisionHash=snapshot['revisionHash']))
    raw_binding=canonical_hash(dict(sourceCandidate=raw,actionTypeRevisionHash=snapshot['revisionHash']))
    assert typed_binding!=raw_binding
    assert approved.proposal.action_binding_hash==typed_binding
    command,_,_=native_signed_source[1]()
    command=command.model_copy(update=dict(idempotency_key='source-domain-native-'+uuid4().hex,
        approved_proposal=command.approved_proposal.model_copy(update=dict(asset_id=approved.proposal.id,
            revision=approved.proposal.version,content_hash=approved.proposal.proposal_hash)),
        approval_event=command.approval_event.model_copy(update=dict(asset_id=approved.approvals[0].id,
            content_hash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True))))))
    with connect_capacity_issuer(native_signed_source[4],SCOPE) as issuer:
        assert issuer.pgconn.used_password is True
        identity=issuer.execute('SELECT current_database() AS database,session_user AS role').fetchone()
        claims=read_capacity_approved_claims(issuer,command)
        assert claims.source==normalized and claims.maker==maker.subject
        assert claims.approved_proposal==command.approved_proposal
        assert claims.approval_event==command.approval_event
        assert claims.supplier_verified is False and claims.execution_allowed is False
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,maker=maker.subject,
        proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
        proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
        approval_event_hash=command.approval_event.content_hash)
    raw_binding_predicate="""AND p.action_binding_hash=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
      public.canonical_asset_registry_jsonb(pg_catalog.jsonb_build_object(
        'sourceCandidate',p.payload->'sourceCandidate',
        'actionTypeRevisionHash',p.action_type_snapshot->'revisionHash')),'UTF8')),'hex')
    FOR SHARE OF p"""
    naive_statement=CAPACITY_APPROVED_SOURCE_ROW_SQL.replace('FOR SHARE OF p',raw_binding_predicate)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        import json
        from psycopg.types.json import Jsonb
        assert owner.execute('SELECT aos_capacity_publication_private.read_original_source_candidate(%s) AS value',
            (Jsonb(raw),)).fetchone()['value']==normalized.model_dump(mode='json',by_alias=True)
        current=owner.execute(CAPACITY_APPROVED_SOURCE_ROW_SQL,params).fetchone()
        assert current is not None and current['action_binding_hash']==typed_binding
        native_current=owner.execute(CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,params).fetchone()
        assert native_current is not None and native_current['action_binding_hash']==typed_binding
        # Counterfactual only: installing this raw hash predicate would reject
        # the legitimate original approval proven by the private reader above.
        assert owner.execute(naive_statement,params).fetchone() is None
        owner.rollback()  # isolated_owner otherwise commits successful DDL.
    import json
    with capsys.disabled():
        print('CAPACITY_SOURCE_TYPED_BINDING_PROOF '+json.dumps(dict(
            representation=representation,database=identity['database'],issuer_role=identity['role'],
            scram_used=True,proposal_id=command.approved_proposal.asset_id,
            proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
            approval_event_hash=command.approval_event.content_hash,raw_binding_hash=raw_binding,
            typed_binding_hash=typed_binding,private_normalized_claim=True,native_snapshot_positive=True,
            naive_raw_binding_rejected=True,current_database_accessed=False,
            supplier_verified=False,execution_allowed=False),sort_keys=True))


def test_original_source_time_profile_matches_original_datetime_oracle(native_signed_source):
    """Real SQL profile must preserve original accepted values, never broaden them."""
    from datetime import datetime
    from pydantic import TypeAdapter, ValidationError
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL

    oracle = TypeAdapter(datetime)
    values = [
        '2026-10-07T00:01:02Z', '2026-10-07t00:01:02z',
        '2026-10-07 00:01:02+0800', '2026-10-07T00:01Z',
        '2026-10-07T00:01:02.123456789Z', '2026-10-07T00:01:02,5Z',
        '2026-10-07T00:01:02.1+00:00', '2026-10-07T00:01:02-05:30',
        '1791302400', '1791302400000', '1791302400.123456',
        '1791302400000.5', '1.7913024e9', '+1791302400', '-0.000001',
        '20000000000.5', 20000000000.5, -20000000000.5,
        20000000000, 20000000001, -20000000000, -20000000001,
        1791302400.123457, '1791302400.999999',
        None, True, {}, [], 'NaN', 'Infinity', ' 1791302400 ',
        '2026-10-07', '2026-10-07T00:01:02', '2026-10-07T00:01.5Z',
        '2026-10-07T00:01:02+08', '2026-10-07T00:01:02+08:00:01',
        '2026-10-07T24:01:02Z', '2026-10-07T00:01:60Z',
        '2026-02-30T00:01:02Z', '0000-10-07T00:01:02Z',
        '2026-10-07T00:01:02+24:00', '2026-10-07T00:01:02+08:60',
    ]
    mismatches = []
    with isolated_owner() as owner:
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        rows = owner.execute("""SELECT p.provolatile,p.prosecdef,p.proisstrict,
            r.rolname,p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_roles r ON r.oid=p.proowner
            WHERE n.nspname='aos_capacity_publication_private'
            AND p.proname IN ('original_source_field','original_source_ref',
                'original_source_time','read_original_source_candidate')""").fetchall()
        assert len(rows) == 4
        assert all(r['provolatile']=='i' and not r['prosecdef'] and r['proisstrict']
            and r['rolname']=='aos_capacity_publication_owner'
            and r['proconfig']==['search_path=pg_catalog'] for r in rows)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for value in values:
            try:
                parsed = oracle.validate_python(value)
                expected = oracle.dump_python(parsed, mode='json') if parsed.utcoffset() is not None else None
            except ValidationError:
                expected = None
            try:
                with owner.transaction():
                    actual = owner.execute('SELECT canonical FROM aos_capacity_publication_private.original_source_time(%s)',
                        (Jsonb(value),)).fetchone()['canonical']
            except psycopg.Error as error:
                assert error.sqlstate == '22023'
                actual = None
            if actual != expected:
                mismatches.append((value, expected, actual))
        owner.rollback()
        assert owner.execute("""SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='aos_capacity_publication_private'
            AND p.proname IN ('original_source_field','original_source_ref',
                'original_source_time','read_original_source_candidate')""").fetchone()['n'] == 0
        owner.rollback()
    assert not mismatches, f'Original datetime/native SQL incompatibilities: {mismatches!r}'


def test_original_source_candidate_profile_matches_original_shape_oracle(native_signed_source):
    from copy import deepcopy
    from pydantic import ValidationError
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourceCandidate
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL

    baseline = native_signed_source[3].model_dump(mode='json', by_alias=True)
    cases = [('baseline', baseline)]
    for label, field, value in [
        ('unknown', 'extra', 1), ('schema_float', 'schemaVersion', 1.0),
        ('schema_bool', 'schemaVersion', True), ('execution_int', 'executionAllowed', 0),
        ('execution_true', 'executionAllowed', True), ('naive', 'validFrom', '2026-10-07T00:00:00'),
        ('equal_window', 'validUntil', baseline['validFrom']), ('null_ref', 'basisRef', None),
    ]:
        candidate = deepcopy(baseline)
        candidate[field] = value
        cases.append((label, candidate))
    for label, field, value in [
        ('ref_revision_string', 'revision', '1'), ('ref_revision_float', 'revision', 1.0),
        ('ref_revision_bool', 'revision', True), ('ref_hash_upper', 'contentHash', 'A'*64),
        ('ref_kind', 'assetType', 'EvidenceBundleRevision'), ('ref_trim', 'assetId', ' padded '),
        ('ref_internal_space', 'assetId', 'internal space'), ('ref_unicode', 'assetId', '账户😀'),
        ('ref_extra', 'unknown', 1),
    ]:
        candidate = deepcopy(baseline)
        candidate['physicalAccountRef'][field] = value
        cases.append((label, candidate))
    mismatches = []
    with isolated_owner() as owner:
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        assert owner.execute("""SELECT count(*) AS n FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace,
            LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
            WHERE n.nspname='aos_capacity_publication_private'
            AND p.proname IN ('original_source_field','original_source_ref',
                'original_source_time','read_original_source_candidate')
            AND a.grantee=0 AND a.privilege_type='EXECUTE'""").fetchone()['n'] == 0
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for label, candidate in cases:
            try:
                expected = ProviderCapacitySourceCandidate.model_validate(candidate).model_dump(mode='json', by_alias=True)
            except ValidationError:
                expected = None
            try:
                with owner.transaction():
                    actual = owner.execute('SELECT aos_capacity_publication_private.read_original_source_candidate(%s) AS value',
                        (Jsonb(candidate),)).fetchone()['value']
            except psycopg.Error as error:
                assert error.sqlstate == '22023'
                actual = None
            if actual != expected:
                mismatches.append((label, expected is not None, actual is not None))
        owner.rollback()
    assert not mismatches, f'Original candidate/native SQL incompatibilities: {mismatches!r}'


def test_native_source_binding_rejects_coherent_wrong_hash(native_signed_source):
    """Matching hashes do not replace the original typed candidate calculation."""
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,CAPACITY_APPROVED_SOURCE_ROW_SQL,
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_APPROVAL_EVENT_PROJECTION_SQL)
    _,actual_command,_,source,_=native_signed_source
    command,_,_=actual_command()
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
        maker=authenticate_capacity_issuance_command(command).subject,
        proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
        proposal_hash=command.approved_proposal.content_hash,
        approval_event_id=command.approval_event.asset_id,approval_event_hash=command.approval_event.content_hash)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        original=owner.execute(CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,params).fetchone()
        assert original is not None
        expected=canonical_hash(dict(sourceCandidate=source.model_dump(mode='json',by_alias=True),
            actionTypeRevisionHash=original['action_type_snapshot']['revisionHash']))
        assert original['action_binding_hash']==expected
        owner.execute('RESET ROLE')
        original_event_hash=params['approval_event_hash']
        original_proposal_hash=params['proposal_hash']
        owner.execute('SAVEPOINT coherent_binding_fault')
        try:
            snapshot=owner.execute('SELECT snapshot FROM public.aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (*SCOPE.key,original['proposal_id'])).fetchone()['snapshot']
            wrong='a'*64 if expected!='a'*64 else 'b'*64
            snapshot['actionBindingHash']=wrong
            changed_proposal_hash=canonical_hash(snapshot)
            # Isolated test-admin historical corruption only, rolled back.
            # Every dependent stored hash is updated to stay coherent.
            owner.execute("SET LOCAL session_replication_role='replica'")
            owner.execute('UPDATE public.aip_action_draft SET snapshot=%s WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (Jsonb(snapshot),*SCOPE.key,original['proposal_id']))
            owner.execute('UPDATE public.aip_action_proposal SET action_binding_hash=%s,proposal_hash=%s '
                'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (wrong,changed_proposal_hash,*SCOPE.key,original['proposal_id']))
            owner.execute('UPDATE public.aip_action_approval_event SET action_binding_hash=%s,proposal_hash=%s '
                'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
                (wrong,changed_proposal_hash,*SCOPE.key,params['approval_event_id']))
            owner.execute("SET LOCAL session_replication_role='origin'")
            params['proposal_hash']=changed_proposal_hash
            params['approval_event_hash']=owner.execute(CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,params).fetchone()['hash']
            assert params['approval_event_hash']!=original_event_hash
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            # Same-version control proves snapshot/hash consistency alone still
            # matches; only the added original typed calculation rejects it.
            assert owner.execute(CAPACITY_APPROVED_SOURCE_ROW_SQL,params).fetchone() is not None
            assert owner.execute(CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,params).fetchone() is None, (
                'Native Source must recompute original typed binding even when all stored hashes agree')
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT coherent_binding_fault')
            params['approval_event_hash']=original_event_hash
            params['proposal_hash']=original_proposal_hash
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,params).fetchone() is not None

        owner.rollback()  # Never persist temporary private profile functions.


def test_native_original_capacity_application_profile_matches_original_model(native_signed_source):
    from copy import deepcopy
    from datetime import timedelta, timezone
    from pydantic import ValidationError
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL)

    source = native_signed_source[3]
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        baseline = owner.execute('SELECT request_json FROM public.aip_provider_capacity_request WHERE org_id=%s AND project_id=%s AND request_id=%s',
            (*SCOPE.key,source.allocation_request_ref.asset_id)).fetchone()['request_json']['application']
        model = ProviderCapacityRequest.model_validate(baseline)
        cases = [('baseline',baseline)]
        for label,field,value in [
            ('extra','unknown',1),('schema_float','schemaVersion',1.0),('schema_bool','schemaVersion',True),
            ('concurrency_string','requestedMaxConcurrency','2'),('concurrency_float','requestedMaxConcurrency',2.0),
            ('concurrency_bool','requestedMaxConcurrency',True),('concurrency_zero','requestedMaxConcurrency',0),
            ('concurrency_over','requestedMaxConcurrency',1000001),('token_over','requestedMaxTokenUnits',1000000000001),
            ('token_float','requestedMaxTokenUnits',1.0),('unit','tokenUnit','tokens'),('basis','basisKind','owner_allocation'),
            ('account_trim','physicalAccountId',' padded '),('account_nbsp','physicalAccountId','\u00a0alias'),
            ('account_space','physicalAccountId','internal space'),('account_unicode','physicalAccountId','账户😀'),
            ('account_zero_width','physicalAccountId','a\u200bb'),('account_bool','physicalAccountId',True),
            ('account_empty','physicalAccountId',''),('account_long','physicalAccountId','a'*201),
            ('naive','validFrom','2026-10-07T00:00:00'),('equal_start','validFrom',baseline['proposalExpiresAt']),
            ('expiry_after_until','proposalExpiresAt',(model.valid_until+timedelta(seconds=1)).isoformat()),
            ('window_over','validUntil',(model.valid_from+timedelta(days=367)).isoformat()),('null_time','validUntil',None),
            ('canary','tenant',dict(orgId='dev-org',projectId='dev-project')),
        ]:
            value_body=deepcopy(baseline);value_body[field]=value;cases.append((label,value_body))
        value_body=deepcopy(baseline);del value_body['tokenUnit'];cases.append(('missing',value_body))
        value_body=deepcopy(baseline);value_body['schema_version']=1;cases.append(('duplicate_alias',value_body))
        value_body=deepcopy(baseline)
        value_body['providerRef']={dict(assetType='asset_type',assetId='asset_id',contentHash='content_hash').get(k,k):v
            for k,v in value_body['providerRef'].items()}
        cases.append(('nested_alias',value_body))
        value_body=model.model_dump(mode='json',by_alias=False);cases.append(('top_alias',value_body))
        value_body=deepcopy(baseline)
        for field,attribute in [('validFrom','valid_from'),('validUntil','valid_until'),('proposalExpiresAt','proposal_expires_at')]:
            value_body[field]=getattr(model,attribute).astimezone(timezone(timedelta(hours=8))).isoformat(sep=' ')
        cases.append(('offset_space',value_body))
        value_body=deepcopy(baseline)
        for field,attribute in [('validFrom','valid_from'),('validUntil','valid_until'),('proposalExpiresAt','proposal_expires_at')]:
            value_body[field]=str(int(getattr(model,attribute).timestamp()))
        cases.append(('epoch_strings',value_body))
        value_body=deepcopy(baseline);value_body['providerRef']['assetType']='EvidenceBundleRevision';cases.append(('ref_kind',value_body))
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute(CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL)
        flags=owner.execute("""SELECT p.provolatile,p.proisstrict,p.prosecdef,p.proconfig,r.rolname,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_exec,
            has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_exec,
            EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_exec
            FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
            WHERE p.oid=to_regprocedure('aos_capacity_publication_private.read_original_capacity_application(jsonb)')""").fetchone()
        assert flags['provolatile']=='i' and flags['proisstrict'] and not flags['prosecdef']
        assert flags['proconfig']==['search_path=pg_catalog'] and flags['rolname']=='aos_capacity_publication_owner'
        assert not flags['runtime_exec'] and not flags['issuer_exec'] and not flags['public_exec']
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        mismatches=[]
        for label,value_body in cases:
            try:
                expected=ProviderCapacityRequest.model_validate(value_body).model_dump(mode='json',by_alias=True)
            except ValidationError:
                expected=None
            try:
                with owner.transaction():
                    actual=owner.execute('SELECT aos_capacity_publication_private.read_original_capacity_application(%s) AS value',
                        (Jsonb(value_body),)).fetchone()['value']
            except psycopg.Error as error:
                assert error.sqlstate=='22023'
                actual=None
            if expected!=actual:mismatches.append((label,expected is not None,actual is not None))
        owner.rollback()
        assert owner.execute("SELECT to_regprocedure('aos_capacity_publication_private.read_original_capacity_application(jsonb)') AS fn").fetchone()['fn'] is None
        owner.rollback()
    assert not mismatches, f'Original application/native incompatibilities: {mismatches!r}'


def test_native_original_capacity_request_rechecks_exact_row_expiry(native_signed_source):
    from datetime import timedelta
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,
        CAPACITY_REQUEST_ROW_SQL,CAPACITY_NATIVE_REQUEST_ROW_SQL)
    _,actual_command,_,source,_=native_signed_source
    command,_,_=actual_command()
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
        request_id=source.allocation_request_ref.asset_id,request_hash=source.allocation_request_ref.content_hash,
        maker=authenticate_capacity_issuance_command(command).subject)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute(CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        original=owner.execute(CAPACITY_NATIVE_REQUEST_ROW_SQL,params).fetchone()
        assert original is not None
        assert owner.execute(CAPACITY_NATIVE_REQUEST_ROW_SQL,{**params,'maker':'wrong-native-maker'}).fetchone() is None
        owner.execute('RESET ROLE')
        owner.execute('SAVEPOINT exact_expiry_fault')
        try:
            # Original145 CHECK already prevents this mismatch on runtime INSERT.
            # Simulate isolated schema+data corruption solely inside this savepoint.
            checks=owner.execute("SELECT conname FROM pg_constraint WHERE conrelid='public.aip_provider_capacity_request'::regclass AND contype='c' AND pg_get_constraintdef(oid) LIKE '%proposalExpiresAt%' AND pg_get_constraintdef(oid) LIKE '%timestamp with time zone = expires_at%'").fetchall()
            assert len(checks)==1
            from psycopg import sql
            owner.execute(sql.SQL('ALTER TABLE public.aip_provider_capacity_request DROP CONSTRAINT {}').format(sql.Identifier(checks[0]['conname'])))
            owner.execute("SET LOCAL session_replication_role='replica'")
            owner.execute('UPDATE public.aip_provider_capacity_request SET expires_at=%s WHERE org_id=%s AND project_id=%s AND request_id=%s',
                (original['expires_at']+timedelta(seconds=1),*SCOPE.key,params['request_id']))
            owner.execute("SET LOCAL session_replication_role='origin'")
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert owner.execute(CAPACITY_REQUEST_ROW_SQL,params).fetchone() is not None
            assert owner.execute(CAPACITY_NATIVE_REQUEST_ROW_SQL,params).fetchone() is None
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT exact_expiry_fault')
        assert owner.execute("SELECT count(*) AS n FROM pg_constraint WHERE conrelid='public.aip_provider_capacity_request'::regclass AND contype='c' AND pg_get_constraintdef(oid) LIKE '%proposalExpiresAt%' AND pg_get_constraintdef(oid) LIKE '%timestamp with time zone = expires_at%'").fetchone()['n']==1
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(CAPACITY_NATIVE_REQUEST_ROW_SQL,params).fetchone() is not None
        owner.rollback()


@pytest.mark.parametrize('kind',['account','basis'])
def test_native_original_candidate_profile_matches_original_model(native_signed_source,kind):
    from copy import deepcopy
    from datetime import timedelta,timezone
    from pydantic import ValidationError
    from psycopg.types.json import Jsonb
    from psycopg import sql
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL
    source=native_signed_source[3]
    ref=source.physical_account_ref if kind=='account' else source.basis_ref
    model=ProviderPhysicalAccountCandidate if kind=='account' else ProviderCapacityBasisCandidate
    function='read_original_physical_account' if kind=='account' else 'read_original_capacity_basis'
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        raw=owner.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE org_id=%s AND project_id=%s AND candidate_id=%s AND revision=%s',
            (*SCOPE.key,ref.asset_id,ref.revision)).fetchone()['request_json']['candidate']
        baseline=model.model_validate(raw)
        cases=[('original_row',raw),('all_snake',baseline.model_dump(mode='json',by_alias=False))]
        changes=[('extra','unknown',1),('schema_bool','schemaVersion',True),('schema_float','schemaVersion',1.0),
            ('schema_two','schemaVersion',2),('canary','tenant',dict(orgId='dev-org',projectId='dev-project')),
            ('tenant_null','tenant',None)]
        if kind=='account':
            providers=raw['providerRefs']
            changed=deepcopy(providers[0]);changed['revision']+=1
            changes += [
                ('identity_trim','physicalAccountId',' padded '),('identity_null','physicalAccountId',None),
                ('identity_inside','physicalAccountId','account \u200b账户😀'),('identity_long','physicalAccountId','a'*201),
                ('supplier_trim','supplierId','supplier\u00a0'),('supplier_inside','supplierId','supplier 中间'),
                ('fingerprint_upper','supplierAccountFingerprint','A'*64),('fingerprint_newline','supplierAccountFingerprint','a'*64+'\n'),
                ('fingerprint_number','supplierAccountFingerprint',1),('providers_empty','providerRefs',[]),
                ('providers_duplicate','providerRefs',[providers[0],providers[0]]),
                ('providers_same_id_new_revision','providerRefs',[providers[0],changed]),
                ('providers_over','providerRefs',providers*1001),('providers_scalar','providerRefs',{}),
                ('provider_null','providerRefs',[None]),('evidence_null','evidenceRef',None),
            ]
            alias=deepcopy(raw)
            alias['providerRefs']=[{dict(assetType='asset_type',assetId='asset_id',contentHash='content_hash').get(k,k):v
                for k,v in entry.items()} for entry in providers]
            cases.append(('provider_alias',alias))
        else:
            changes += [
                ('basis_supplier','basisKind','supplier_limit_claim'),('basis_null','basisKind',None),
                ('basis_wrong','basisKind','owner_requested_allocation'),('concurrency_bool','maxConcurrency',True),
                ('concurrency_float','maxConcurrency',2.0),('concurrency_string','maxConcurrency','2'),
                ('concurrency_zero','maxConcurrency',0),('concurrency_over','maxConcurrency',1000001),
                ('observed_naive','observedAt','2026-10-07T00:00:00'),
                ('observed_before_start','observedAt',(baseline.valid_from-timedelta(days=1000)).isoformat()),
                ('observed_after_until','observedAt',(baseline.valid_until+timedelta(seconds=1)).isoformat()),
                ('equal_window','validFrom',raw['validUntil']),
                ('large_window','validUntil',(baseline.valid_from+timedelta(days=367)).isoformat()),
                ('token_null','tokenLimit',None),
                ('token_float','tokenLimit',dict(mode='inflight_upper_bound',unit='token',maxTokens=1.0)),
                ('token_max','tokenLimit',dict(mode='inflight_upper_bound',unit='token',maxTokens=1000000000000)),
                ('token_over','tokenLimit',dict(mode='inflight_upper_bound',unit='token',maxTokens=1000000000001)),
                ('token_bool','tokenLimit',dict(mode='inflight_upper_bound',unit='token',maxTokens=True)),
                ('token_unit','tokenLimit',dict(mode='inflight_upper_bound',unit='tokens',maxTokens=1)),
                ('token_mode','tokenLimit',dict(mode='other',unit='token',maxTokens=1)),
                ('token_extra','tokenLimit',dict(mode='inflight_upper_bound',unit='token',maxTokens=1,windowSeconds=1)),
            ]
            fixed=dict(mode='fixed_window_rate',unit='token',maxTokens=100,windowSeconds=60,windowAnchor=raw['validFrom'])
            changes.append(('fixed_valid','tokenLimit',fixed))
            for label,field,value in [('fixed_zero','windowSeconds',0),('fixed_over','windowSeconds',86401),
                ('fixed_bool','windowSeconds',True),('fixed_float','windowSeconds',60.0),
                ('fixed_naive','windowAnchor','2026-10-07T00:00:00'),
                ('fixed_epoch','windowAnchor',str(int(baseline.valid_from.timestamp())))]:
                candidate=deepcopy(fixed);candidate[field]=value;changes.append((label,'tokenLimit',candidate))
            alias=deepcopy(raw)
            alias['physicalAccountRef']={dict(assetType='asset_type',assetId='asset_id',contentHash='content_hash').get(k,k):v
                for k,v in alias['physicalAccountRef'].items()}
            cases.append(('account_ref_alias',alias))
            offset=deepcopy(raw)
            for field,attribute in [('validFrom','valid_from'),('validUntil','valid_until'),('observedAt','observed_at')]:
                offset[field]=getattr(baseline,attribute).astimezone(timezone(timedelta(hours=8))).isoformat(sep=' ')
            cases.append(('offset_space',offset))
        for label,field,value in changes:
            candidate=deepcopy(raw);candidate[field]=value;cases.append((label,candidate))
        duplicate=deepcopy(raw);duplicate['schema_version']=1;cases.append(('duplicate_alias',duplicate))
        missing=deepcopy(raw);del missing['evidenceRef'];cases.append(('missing',missing))
        owner.execute(CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute(CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL)
        names=['original_claim_fields','original_claim_header','original_claim_identity','original_claim_integer',
            'read_original_token_limit','read_original_physical_account','read_original_capacity_basis']
        flags=owner.execute("""SELECT p.provolatile,p.proisstrict,p.prosecdef,p.proconfig,r.rolname,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_exec,
            has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_exec,
            EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_exec
            FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)""",(names,)).fetchall()
        assert len(flags)==7
        assert all(f['provolatile']=='i' and f['proisstrict'] and not f['prosecdef']
            and f['proconfig']==['search_path=pg_catalog'] and f['rolname']=='aos_capacity_publication_owner'
            and not f['runtime_exec'] and not f['issuer_exec'] and not f['public_exec'] for f in flags)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        mismatches=[]
        for label,candidate in cases:
            try:expected=model.model_validate(candidate).model_dump(mode='json',by_alias=True)
            except ValidationError:expected=None
            try:
                with owner.transaction():
                    actual=owner.execute(sql.SQL('SELECT aos_capacity_publication_private.{}(%s) AS value').format(sql.Identifier(function)),
                        (Jsonb(candidate),)).fetchone()['value']
            except psycopg.Error as error:
                assert error.sqlstate=='22023';actual=None
            if expected!=actual:mismatches.append((label,expected is not None,actual is not None))
        owner.rollback()
        assert owner.execute("SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)",
            (names,)).fetchone()['n']==0
        owner.rollback()
    assert not mismatches, f'Original {kind}/native incompatibilities: {mismatches!r}'


def test_native_original_candidate_rows_and_combination_keep_original_claims(native_signed_source):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,
        CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_NATIVE_CANDIDATE_ROW_SQL,
        CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,CAPACITY_SOURCE_COMBINATION_SQL)
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    _,actual_command,_,source,_=native_signed_source
    command,_,_=actual_command();maker=authenticate_capacity_issuance_command(command).subject
    params=ProviderCapacitySourceActionGuard._combination_params(SCOPE,source,maker)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for kind,ref,model in [('account',source.physical_account_ref,ProviderPhysicalAccountCandidate),('basis',source.basis_ref,ProviderCapacityBasisCandidate)]:
            row=owner.execute(CAPACITY_NATIVE_CANDIDATE_ROW_SQL,dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
                candidate_id=ref.asset_id,revision=ref.revision,candidate_kind=kind,content_hash=ref.content_hash,maker=maker)).fetchone()
            assert row is not None and row['content_hash']==ref.content_hash and row['actual_hash']==ref.content_hash
            assert row['normalized_candidate']==model.model_validate(row['request_json']['candidate']).model_dump(mode='json',by_alias=True)
            assert row['basis_verified'] is False and row['execution_allowed'] is False
        assert owner.execute(CAPACITY_SOURCE_COMBINATION_SQL,params).fetchone() is not None
        assert owner.execute(CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,params).fetchone() is not None
        assert owner.execute(CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,{**params,'maker':'wrong-native-maker'}).fetchone() is None
        owner.rollback()


@pytest.mark.parametrize('representation',['basis_account','account_provider','basis_mixed','provider_mixed','basis_epoch','token_alias'])
def test_native_candidate_combination_preserves_real_original_private_approval(native_signed_source,approved_command,representation,capsys):
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from aos_api.db import connect_serializable
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_action import (
        propose_provider_capacity_source,decide_provider_capacity_source,ProviderCapacitySourceActionGuard)
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,
        CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,
        CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL)
    maker,checker=approved_command[:2];source=native_signed_source[3]
    with connect_serializable(SCOPE) as runtime:
        account=runtime.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',
            (source.physical_account_ref.asset_id,)).fetchone()['request_json']
        basis=runtime.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',
            (source.basis_ref.asset_id,)).fetchone()['request_json']
        mapping=dict(assetId='asset_id') if representation.endswith('mixed') else dict(assetType='asset_type',assetId='asset_id',contentHash='content_hash')
        if representation in {'account_provider','provider_mixed'}:
            account['candidate']['providerRefs'][0]={mapping.get(k,k):v for k,v in account['candidate']['providerRefs'][0].items()}
        account_id='native-domain-account-'+uuid4().hex;account_hash=canonical_hash(account)
        account_ref=source.physical_account_ref.model_copy(update=dict(asset_id=account_id,content_hash=account_hash))
        basis['candidate']['physicalAccountRef']=account_ref.model_dump(by_alias=True)
        if representation in {'basis_account','basis_mixed'}:
            basis['candidate']['physicalAccountRef']={mapping.get(k,k):v for k,v in basis['candidate']['physicalAccountRef'].items()}
        if representation=='basis_epoch':
            parsed=ProviderCapacityBasisCandidate.model_validate(basis['candidate'])
            for field,attribute in [('validFrom','valid_from'),('validUntil','valid_until'),('observedAt','observed_at')]:
                basis['candidate'][field]=str(int(getattr(parsed,attribute).timestamp()))
        if representation=='token_alias':
            basis['candidate']['tokenLimit']['max_tokens']=basis['candidate']['tokenLimit'].pop('maxTokens')
        normalized_basis=ProviderCapacityBasisCandidate.model_validate(basis['candidate'])
        basis_id='native-domain-basis-'+uuid4().hex;basis_hash=canonical_hash(basis)
        for kind,identifier,body,digest in [('account',account_id,account,account_hash),('basis',basis_id,basis,basis_hash)]:
            runtime.execute('INSERT INTO public.aip_provider_capacity_candidate '
                '(org_id,project_id,candidate_id,candidate_kind,idempotency_key,content_hash,request_json,created_by) '
                'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (*SCOPE.key,identifier,kind,'native-domain-'+uuid4().hex,digest,Jsonb(body),maker.subject))
        runtime.commit()
    changed=source.model_copy(update=dict(physical_account_ref=account_ref,
        basis_ref=source.basis_ref.model_copy(update=dict(asset_id=basis_id,content_hash=basis_hash)),
        valid_until=min(source.valid_until,normalized_basis.valid_until)))
    proposal=propose_provider_capacity_source(maker,changed,'native-domain-review-'+uuid4().hex,changed.valid_until)
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'native-domain-checker-'+uuid4().hex,
        DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
            expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',
            reason='isolated original native candidate acceptance',approvalExpiresAt=changed.valid_until))
    command,_,_=native_signed_source[1]()
    command=command.model_copy(update=dict(idempotency_key='native-domain-read-'+uuid4().hex,
        approved_proposal=command.approved_proposal.model_copy(update=dict(asset_id=approved.proposal.id,
            revision=approved.proposal.version,content_hash=approved.proposal.proposal_hash)),
        approval_event=command.approval_event.model_copy(update=dict(asset_id=approved.approvals[0].id,
            content_hash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True))))))
    with connect_capacity_issuer(native_signed_source[4],SCOPE) as issuer:
        assert issuer.pgconn.used_password is True
        claims=read_capacity_approved_claims(issuer,command)
        assert claims.source==changed and claims.maker==maker.subject
        assert claims.supplier_verified is False and claims.execution_allowed is False
    params=ProviderCapacitySourceActionGuard._combination_params(SCOPE,changed,maker.subject)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,params).fetchone() is not None
        assert owner.execute(CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,maker=maker.subject,
            proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
            proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
            approval_event_hash=command.approval_event.content_hash)).fetchone() is not None
        owner.rollback()
    import json
    with capsys.disabled():
        print('CAPACITY_NATIVE_CANDIDATE_COMBINATION_PROOF '+json.dumps(dict(representation=representation,
            proposal_id=approved.proposal.id,proposal_hash=approved.proposal.proposal_hash,
            approval_event_id=command.approval_event.asset_id,approval_event_hash=command.approval_event.content_hash,
            account_raw_hash=account_hash,basis_raw_hash=basis_hash,actual_runtime_insert=True,
            original_independent_approval=True,native_scram_claims=True,native_source_binding=True,
            native_original_combination=True,source_published=False,current_database_accessed=False),sort_keys=True))


def test_native_candidate_combination_rejects_rehashed_original_row_term_faults(native_signed_source):
    from copy import deepcopy
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,
        CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_NATIVE_SOURCE_COMBINATION_SQL)
    _,actual_command,_,source,_=native_signed_source
    command,_,_=actual_command();maker=authenticate_capacity_issuance_command(command).subject
    params=ProviderCapacitySourceActionGuard._combination_params(SCOPE,source,maker)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        account=owner.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',
            (source.physical_account_ref.asset_id,)).fetchone()['request_json']
        basis=owner.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',
            (source.basis_ref.asset_id,)).fetchone()['request_json']
        request=owner.execute('SELECT request_json FROM public.aip_provider_capacity_request WHERE request_id=%s',
            (source.allocation_request_ref.asset_id,)).fetchone()['request_json']['application']
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,params).fetchone() is not None
        for fault in ['account_alias','basis_ref','provider_member','concurrency']:
            owner.execute('RESET ROLE');owner.execute('SAVEPOINT original_term_fault')
            try:
                a,b=deepcopy(account),deepcopy(basis)
                if fault=='account_alias':a['candidate']['physicalAccountId']='different-original-alias'
                elif fault=='provider_member':a['candidate']['providerRefs'][0]['assetId']='different-provider-member'
                elif fault=='concurrency':b['candidate']['maxConcurrency']=request['requestedMaxConcurrency']+1
                account_hash=canonical_hash(a)
                b['candidate']['physicalAccountRef']['contentHash']=account_hash
                if fault=='basis_ref':b['candidate']['physicalAccountRef']['assetId']='different-original-account'
                basis_hash=canonical_hash(b)
                # Models still valid: only original cross-row terms have changed.
                ProviderPhysicalAccountCandidate.model_validate(a['candidate'])
                ProviderCapacityBasisCandidate.model_validate(b['candidate'])
                owner.execute("SET LOCAL session_replication_role='replica'")
                for body,digest,identifier in [(a,account_hash,params['account_id']),(b,basis_hash,params['basis_id'])]:
                    owner.execute('UPDATE public.aip_provider_capacity_candidate SET request_json=%s,content_hash=%s WHERE org_id=%s AND project_id=%s AND candidate_id=%s',
                        (Jsonb(body),digest,*SCOPE.key,identifier))
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert owner.execute(CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,{**params,'account_hash':account_hash,'basis_hash':basis_hash}).fetchone() is None,fault
            finally:owner.execute('ROLLBACK TO SAVEPOINT original_term_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert owner.execute(CAPACITY_NATIVE_SOURCE_COMBINATION_SQL,params).fetchone() is not None
        owner.rollback()


def test_native_original_provider_profile_preserves_actual_business_hash(native_signed_source):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_action_store import canonical_hash
    from psycopg.types.json import Jsonb
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_NATIVE_PROVIDER_ROW_SQL)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        row=owner.execute("SELECT r.payload,r.content_hash FROM public.aip_provider_instance_head h JOIN public.aip_provider_instance_revision r USING(org_id,project_id,provider_instance_id) WHERE h.org_id=%s AND h.project_id=%s AND r.revision=h.current_revision LIMIT 1",SCOPE.key).fetchone()
        assert row is not None
        expected=ProviderInstanceRevision.model_validate(row['payload']).model_dump(mode='json',by_alias=True)
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        actual=owner.execute('SELECT aos_capacity_publication_private.read_original_provider(%s) AS value',(Jsonb(row['payload']),)).fetchone()['value']
        assert actual==expected
        assert canonical_hash({k:v for k,v in actual.items() if k not in AipModelRuntimeStore._META_FIELDS})==row['content_hash']
        params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,provider_id=actual['providerInstanceId'],revision=actual['revision'],content_hash=row['content_hash'])
        assert owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,params).fetchone()['normalized_provider']==expected
        assert owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,{**params,'org_id':'dev-org'}).fetchone() is None
        owner.rollback()
        assert owner.execute("SELECT to_regprocedure('aos_capacity_publication_private.read_original_provider(jsonb)') AS fn").fetchone()['fn'] is None
        owner.rollback()


def test_native_original_provider_profile_matches_original_model_domain(native_signed_source):
    from copy import deepcopy
    from pydantic import ValidationError
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        raw=owner.execute('SELECT payload FROM public.aip_provider_instance_revision WHERE org_id=%s AND project_id=%s LIMIT 1',SCOPE.key).fetchone()['payload']
        base=ProviderInstanceRevision.model_validate(raw)
        cases=[('original',raw),('all_snake',base.model_dump(mode='json',by_alias=False))]
        for label,field,value in [
            ('revision_string','revision',str(base.revision)),('revision_float','revision',float(base.revision)),
            ('revision_true','revision',True),('revision_false','revision',False),('revision_fraction','revision',1.5),
            ('revision_big','revision',9223372036854775808),('revision_big_string','revision','9223372036854775808'),
            ('revision_string_over_digits','revision','1'*4301),('revision_string_zero_padding','revision','0'*4500+'1'),
            ('revision_padded','revision','\u00a0+001\u00a0'),('revision_decimal','revision','01.00'),
            ('revision_underscore','revision','1_0'),('revision_bad_underscore','revision','1__0'),
            ('revision_exponent_string','revision','1e0'),('revision_null','revision',None),
            ('created_naive','createdAt','2026-10-07T00:00:00'),('created_date_only','createdAt','2026-10-07'),
            ('created_naive_minutes','createdAt','2026-10-07 01:02'),
            ('created_naive_fraction','createdAt','2026-10-07T01:02:03,1234567'),
            ('created_epoch','createdAt','1700000000.25'),('created_epoch_number','createdAt',1700000000.25),
            ('created_offset','createdAt','2026-10-07 01:02:03+0800'),('created_null','createdAt',None),
            ('created_invalid','createdAt','2026-02-30T01:00:00'),
            ('actor_spaces','createdBy',' owner '),('actor_null','createdBy',None),
            ('id_spaces','providerInstanceId',' provider '),('id_blank','providerInstanceId',' '),
            ('id_long','providerInstanceId','x'*201),('tenant_canary','tenant',dict(orgId='dev-org',projectId='dev-project')),
            ('tenant_empty','tenant',dict(orgId='',projectId='')),('hash_upper','contentHash','A'*64),
            ('hash_newline','contentHash','a'*64+'\n'),('secret_trim','secretRef',' '+base.secret_ref+'\u00a0'),
            ('secret_prefix_only','secretRef','vault://'),('secret_plain','secretRef','literal-value'),
            ('secret_null','secretRef',None),('secret_version_spaces','secretVersion',' '),
            ('lifecycle_suspended','lifecycle','suspended'),('lifecycle_wrong','lifecycle','disabled'),
            ('extra','unknown',1)]:
            v=deepcopy(raw);v[field]=value;cases.append((label,v))
        for label,field,value in [
            ('timeout_string','timeoutMs',str(base.endpoint_profile.timeout_ms)),
            ('timeout_float','timeoutMs',float(base.endpoint_profile.timeout_ms)),('timeout_bool','timeoutMs',True),
            ('timeout_min','timeoutMs',100),('timeout_max','timeoutMs',3600000),('timeout_over','timeoutMs',3600001),
            ('timeout_fraction','timeoutMs',100.5),('base_space','baseUrl',' '),('region_empty','region',''),
            ('metadata_null','metadata',None),('metadata_empty_values','metadata',{'':'','x':'\u200b'}),
            ('metadata_numeric','metadata',{'key':1}),('metadata_over','metadata',{str(i):'' for i in range(33)}),
            ('secret_shape','apiKey','forbidden')]:
            v=deepcopy(raw);v['endpointProfile'][field]=value;cases.append((label,v))
        v=deepcopy(raw);v['endpointProfile'].pop('metadata',None);cases.append(('metadata_default',v))
        for label,field,value in [('ref_revision_str','revision','01.0'),('ref_revision_bool','revision',True),
            ('ref_id_trim','assetId',' '+raw['pluginRef']['assetId']+' '),('ref_wrong_kind','assetType','AgentTemplateRevision'),
            ('ref_id_blank','assetId',' '),('ref_hash_number','contentHash',1)]:
            v=deepcopy(raw);v['pluginRef'][field]=value;cases.append((label,v))
        for point in [9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8232,8233,8239,8287,12288]:
            v=deepcopy(raw);v['revision']=chr(point)+'1'+chr(point);cases.append(('revision_whitespace_'+str(point),v))
        v=deepcopy(raw);v['provider_instance_id']=raw['providerInstanceId'];cases.append(('duplicate_alias',v))
        v=deepcopy(raw);del v['createdBy'];cases.append(('missing',v))
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL):
            owner.execute(profile)
        names=['original_provider_string','original_provider_integer','original_provider_ref','original_provider_time','read_original_provider']
        flags=owner.execute("""SELECT p.provolatile,p.proisstrict,p.prosecdef,p.proconfig,r.rolname,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_exec,
            has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_exec,
            EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_exec
            FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)""",(names,)).fetchall()
        assert len(flags)==5
        assert all(f['provolatile']=='i' and f['proisstrict'] and not f['prosecdef']
            and f['proconfig']==['search_path=pg_catalog'] and f['rolname']=='aos_capacity_publication_owner'
            and not f['runtime_exec'] and not f['issuer_exec'] and not f['public_exec'] for f in flags)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        mismatches=[]
        for label,value in cases:
            try:expected=ProviderInstanceRevision.model_validate(value).model_dump(mode='json',by_alias=True)
            except ValidationError:expected=None
            try:
                with owner.transaction():
                    actual=owner.execute('SELECT aos_capacity_publication_private.read_original_provider(%s) AS value',(Jsonb(value),)).fetchone()['value']
            except psycopg.Error as error:
                assert error.sqlstate=='22023';actual=None
            if expected!=actual:mismatches.append((label,expected is not None,actual is not None))
        # Keep decimal JSON literals unrounded until PostgreSQL stores JSONB.
        import json
        for number in ['9007199254740993.0','9007199254740995.0','1.23e40','-1.0','1.5','1.0e309']:
            value=deepcopy(raw);value['revision']='RAW_REVISION_NUMBER'
            document=json.dumps(value).replace('"RAW_REVISION_NUMBER"',number)
            stored=owner.execute('SELECT %s::jsonb AS value',(document,)).fetchone()['value']
            try:expected=ProviderInstanceRevision.model_validate(stored).model_dump(mode='json',by_alias=True)
            except ValidationError:expected=None
            try:
                with owner.transaction():
                    actual=owner.execute('SELECT aos_capacity_publication_private.read_original_provider(%s::jsonb) AS value',(document,)).fetchone()['value']
            except psycopg.Error as error:
                assert error.sqlstate=='22023';actual=None
            if expected!=actual:mismatches.append(('raw_decimal_'+number,expected is not None,actual is not None))
        owner.rollback()
        assert owner.execute("SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)",(names,)).fetchone()['n']==0
        owner.rollback()
    assert not mismatches, f'Original Provider/native incompatibilities: {mismatches!r}'


def test_native_original_provider_current_row_rejects_coherent_payload_faults(native_signed_source):
    from copy import deepcopy
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_NATIVE_PROVIDER_ROW_SQL)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        row=owner.execute('SELECT r.* FROM public.aip_provider_instance_head h JOIN public.aip_provider_instance_revision r USING(org_id,project_id,provider_instance_id) WHERE h.org_id=%s AND h.project_id=%s AND r.revision=h.current_revision LIMIT 1',SCOPE.key).fetchone()
        params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,provider_id=row['provider_instance_id'],revision=row['revision'],content_hash=row['content_hash'])
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,params).fetchone() is not None
        for fault,field,value in [('wrong_id','provider_id','absent-provider'),('wrong_revision','revision',row['revision']+1),('wrong_hash','content_hash','f'*64),('canary','org_id','dev-org')]:
            assert owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,{**params,field:value}).fetchone() is None,fault
        for fault,field,value in [('payload_id','providerInstanceId','other-provider'),('payload_revision','revision',row['revision']+1),
            ('payload_hash','contentHash','e'*64),('payload_tenant','tenant',dict(orgId='dev-org',projectId='dev-project')),
            ('payload_lifecycle','lifecycle','suspended'),('business_content','secretVersion','different-secret-version')]:
            owner.execute('RESET ROLE');owner.execute('SAVEPOINT provider_payload_fault')
            try:
                body=deepcopy(row['payload']);body[field]=value
                normalized=ProviderInstanceRevision.model_validate(body).model_dump(mode='json',by_alias=True)
                if fault in {'payload_revision','payload_hash','payload_tenant'}:
                    assert canonical_hash({k:v for k,v in normalized.items() if k not in AipModelRuntimeStore._META_FIELDS})==row['content_hash']
                owner.execute("SET LOCAL session_replication_role='replica'")
                owner.execute('UPDATE public.aip_provider_instance_revision SET payload=%s WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s AND revision=%s',
                    (Jsonb(body),*SCOPE.key,row['provider_instance_id'],row['revision']))
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,params).fetchone() is None,fault
            finally:owner.execute('ROLLBACK TO SAVEPOINT provider_payload_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,params).fetchone() is not None
        owner.rollback()


@pytest.mark.parametrize('order',['reader_first','writer_first'])
def test_native_provider_query_holds_original_head_share_fence(native_signed_source,order):
    from threading import Event,Thread
    import time
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_NATIVE_PROVIDER_ROW_SQL)
    with isolated_owner() as owner:
        row=owner.execute('SELECT r.* FROM public.aip_provider_instance_head h JOIN public.aip_provider_instance_revision r USING(org_id,project_id,provider_instance_id) WHERE h.org_id=%s AND h.project_id=%s AND r.revision=h.current_revision LIMIT 1',SCOPE.key).fetchone()
        owner.rollback()
    params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,provider_id=row['provider_instance_id'],revision=row['revision'],content_hash=row['content_hash'])
    release=Event();reader_ready=Event();writer_ready=Event();reader_done=Event();writer_done=Event();results={}
    def reader():
        try:
            with isolated_owner() as conn:
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
                for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL):conn.execute(profile)
                conn.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                results['reader_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                if order=='writer_first':reader_ready.set()
                assert conn.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,params).fetchone() is not None
                if order=='reader_first':reader_ready.set()
                assert release.wait(12)
                conn.rollback()
            results['reader_rolled_back']=True
        except BaseException as exc:results['reader_error']=type(exc).__name__
        finally:reader_done.set()
    def writer():
        try:
            with isolated_owner() as conn:
                results['writer_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                if order=='reader_first':writer_ready.set()
                # A no-op still acquires the real original head row write lock.
                conn.execute('UPDATE public.aip_provider_instance_head SET current_revision=current_revision WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',
                    (*SCOPE.key,params['provider_id']))
                if order=='writer_first':writer_ready.set()
                assert release.wait(12)
                conn.rollback()
            results['writer_rolled_back']=True
        except BaseException as exc:results['writer_error']=type(exc).__name__
        finally:writer_done.set()
    rt,wt=Thread(target=reader),Thread(target=writer)
    first,ready,second,other_ready=(rt,reader_ready,wt,writer_ready) if order=='reader_first' else (wt,writer_ready,rt,reader_ready)
    first.start();blocked=False
    try:
        assert ready.wait(10),results
        second.start();assert other_ready.wait(10),results
        waiting,holding=('writer_pid','reader_pid') if order=='reader_first' else ('reader_pid','writer_pid')
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            with isolated_owner() as probe:
                blockers=probe.execute('SELECT pg_blocking_pids(%s) AS blockers',(results[waiting],)).fetchone()['blockers']
                probe.rollback()
            if results[holding] in blockers:blocked=True;break
            if reader_done.is_set() or writer_done.is_set():break
            time.sleep(.02)
        assert blocked,'native Provider read did not hold original head SHARE fence'
        assert not reader_done.is_set() and not writer_done.is_set()
    finally:
        release.set();rt.join(10) if rt.ident else None;wt.join(10) if wt.ident else None
    assert not rt.is_alive() and not wt.is_alive()
    assert results.get('reader_rolled_back') and results.get('writer_rolled_back'),results
    with isolated_owner() as owner:
        assert owner.execute("SELECT to_regprocedure('aos_capacity_publication_private.read_original_provider(jsonb)') AS fn").fetchone()['fn'] is None
        assert owner.execute('SELECT current_revision FROM public.aip_provider_instance_head WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',(*SCOPE.key,params['provider_id'])).fetchone()['current_revision']==row['revision']
        owner.rollback()


@pytest.mark.parametrize('fault',[None,'second_head','second_payload_hash','second_payload_revision'])
def test_native_provider_query_checks_real_full_original_account_set(source_inputs,fault):
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner,produce_formal_provider
    from aos_api.db import connect_serializable
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_model_eval_request_store import ModelEvalRequestBlocked
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_NATIVE_PROVIDER_ROW_SQL)
    maker,checker,source,_=source_inputs
    second=produce_formal_provider(SCOPE,maker.subject,'native-whole-provider-'+uuid4().hex)
    with connect_serializable(SCOPE) as runtime:
        account=ProviderPhysicalAccountCandidate.model_validate(runtime.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',(source.physical_account_ref.asset_id,)).fetchone()['request_json']['candidate'])
        basis=ProviderCapacityBasisCandidate.model_validate(runtime.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',(source.basis_ref.asset_id,)).fetchone()['request_json']['candidate'])
    extra=account.provider_refs[0].model_copy(update=dict(asset_id=second.provider_instance_id,revision=second.revision,content_hash=second.content_hash))
    account=account.model_copy(update=dict(provider_refs=[*account.provider_refs,extra]))
    store=ProviderCapacityCandidateStore()
    saved=store.create_account(SCOPE,maker,'native-full-account-'+uuid4().hex,account)
    account_ref=source.physical_account_ref.model_copy(update=dict(asset_id=saved['candidate_id'],content_hash=saved['content_hash']))
    saved_basis=store.create_basis(SCOPE,maker,'native-full-basis-'+uuid4().hex,basis.model_copy(update=dict(physical_account_ref=account_ref)))
    changed=source.model_copy(update=dict(physical_account_ref=account_ref,basis_ref=source.basis_ref.model_copy(update=dict(asset_id=saved_basis['candidate_id'],content_hash=saved_basis['content_hash']))))
    proposal=propose_provider_capacity_source(maker,changed,'native-full-source-'+uuid4().hex,changed.valid_until)
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'native-full-checker-'+uuid4().hex,
        DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,expectedProposalHash=proposal.proposal.proposal_hash,
            decision='approved',reason='isolated original full Provider set',approvalExpiresAt=changed.valid_until))
    assert approved.proposal.status.value=='approved'
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL):owner.execute(profile)
        def native_results():
            return [owner.execute(CAPACITY_NATIVE_PROVIDER_ROW_SQL,dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
                provider_id=ref.asset_id,revision=ref.revision,content_hash=ref.content_hash)).fetchone() is not None
                for ref in sorted(account.provider_refs,key=lambda item:item.asset_id)]
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert all(native_results()) and len(account.provider_refs)==2
        ProviderCapacityCandidateStore._account_dependencies(owner,SCOPE,account)
        if fault:
            owner.execute('RESET ROLE');owner.execute('SAVEPOINT second_original_provider_fault')
            try:
                owner.execute("SET LOCAL session_replication_role='replica'")
                if fault=='second_head':
                    owner.execute('UPDATE public.aip_provider_instance_head SET current_revision=current_revision+1 WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',(*SCOPE.key,second.provider_instance_id))
                else:
                    body=owner.execute('SELECT payload FROM public.aip_provider_instance_revision WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s AND revision=%s',(*SCOPE.key,second.provider_instance_id,second.revision)).fetchone()['payload']
                    body['contentHash' if fault=='second_payload_hash' else 'revision']='0'*64 if fault=='second_payload_hash' else second.revision+1
                    owner.execute('UPDATE public.aip_provider_instance_revision SET payload=%s WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s AND revision=%s',(Jsonb(body),*SCOPE.key,second.provider_instance_id,second.revision))
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                results=native_results()
                assert sum(results)==1,'native checks must include second actual account Provider'
                with pytest.raises(ModelEvalRequestBlocked):ProviderCapacityCandidateStore._account_dependencies(owner,SCOPE,account)
            finally:owner.execute('ROLLBACK TO SAVEPOINT second_original_provider_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert all(native_results())
        owner.rollback()


def test_native_original_build_request_reads_actual_original_provenance(native_signed_source):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_production_contracts import BuildEvidenceBundleRequest
    from psycopg.types.json import Jsonb
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_ORIGINAL_BUILD_PROFILE_SQL)
    with isolated_owner() as owner:
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
                        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_ORIGINAL_BUILD_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        raw=owner.execute('SELECT request_payload FROM public.aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s LIMIT 1',SCOPE.key).fetchone()['request_payload']
        expected=BuildEvidenceBundleRequest.model_validate(raw).model_dump(mode='json',by_alias=True)
        actual=owner.execute('SELECT aos_capacity_publication_private.read_original_build_request(%s) AS value',(Jsonb(raw),)).fetchone()['value']
        assert actual==expected
        owner.rollback()


def test_native_original_build_request_canonical_domain_and_acl(native_signed_source):
    import copy
    from psycopg import Error
    from psycopg.types.json import Jsonb
    from pydantic import ValidationError
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_production_contracts import BuildEvidenceBundleRequest
    from aos_api.aip_production_contract_store import canonical_hash
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_ORIGINAL_BUILD_PROFILE_SQL)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        raw=owner.execute('SELECT request_payload FROM public.aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s LIMIT 1',SCOPE.key).fetchone()['request_payload']
        cases=[('actual-build',copy.deepcopy(raw))]
        def changed(label,path,value):
            document=copy.deepcopy(raw); target=document
            for part in path[:-1]:target=target[part]
            target[path[-1]]=value;cases.append((label,document))
        for key in raw:
            document=copy.deepcopy(raw);del document[key];cases.append(('missing-'+key,document))
            changed('null-'+key,[key],None)
        changed('extra-field',['extra'],False)
        for value in (0,-1,True,'1',1.0,1,9223372036854775808):
            changed('exact-revision-'+repr(value),['briefRef','revision'],value)
        for value in ('',' ','any-kind','x'*80,'x'*81):
            changed('exact-type-'+repr(value),['briefRef','resourceType'],value)
        changed('exact-id-too-long',['briefRef','resourceId'],'x'*201)
        changed('bad-hash',['briefRef','contentHash'],'z'*64)
        changed('empty-items',['itemRefs'],[])
        changed('empty-facts',['requiredFactIds'],[])
        for key in ('requiredFactIds','marking'):
            for values in ([''],[' x '],['x','x'],[1],['内 部'],['x\x1cy']):
                changed(key+'-'+repr(values),[key],values)
        for value in ('2026-10-07T00:00:00','2026-10-07T00:00:00Z',
                      '2026-10-07T00:00:00+08:00','2026-10-07T00:00:00.123456Z',
                      '2026-10-07','2026-10-07 00:00:00Z','2026-10-07T00:00:00+00:00',1):
            changed('cutoff-'+repr(value),['cutoffAt'],value)
        resource={'resourceType':'arbitrary','resourceId':'x','revision':None,'authority':'source'}
        changed('resource-canonical',['subjectRefs'],[resource])
        for key,value in (('resourceType',' x '),('resourceId',''),('authority','\x1cx'),('revision',1)):
            ref={**resource,key:value};changed('resource-'+key,['subjectRefs'],[ref])
        ref=copy.deepcopy(resource);del ref['revision'];changed('resource-missing-revision',['subjectRefs'],[ref])
        changed('license-arbitrary-numbers',['licenseSummary'],{'nested':[1,1.0,1e15,1e-5,True,None,'中文']})
        changed('license-not-object',['licenseSummary'],[])
        for profile in (CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL,
                        CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL,CAPACITY_ORIGINAL_BUILD_PROFILE_SQL):owner.execute(profile)
        names=['original_build_exact_ref','original_build_resource_ref','read_original_build_request']
        rows=owner.execute("""SELECT p.proname,p.provolatile,p.proisstrict,p.prosecdef,p.proconfig,
            pg_get_userbyid(p.proowner) AS owner,
            EXISTS(SELECT 1 FROM aclexplode(p.proacl) WHERE grantee=0 AND privilege_type='EXECUTE') AS public_execute,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
            has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_execute
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)""",(names,)).fetchall()
        assert len(rows)==3
        assert all(row['provolatile']=='i' and row['proisstrict'] and not row['prosecdef']
                   and row['owner']=='aos_capacity_publication_owner'
                   and row['proconfig']==['search_path=pg_catalog']
                   and not row['public_execute'] and not row['runtime_execute'] and not row['issuer_execute'] for row in rows)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        mismatches=[];accepted=0
        for label,document in cases:
            try:
                normalized=BuildEvidenceBundleRequest.model_validate(document).model_dump(mode='json',by_alias=True)
                expected=canonical_hash(normalized)==canonical_hash(document)
            except ValidationError:expected=False
            owner.execute('SAVEPOINT original_build_domain')
            try:
                try:
                    actual=owner.execute('SELECT aos_capacity_publication_private.read_original_build_request(%s) AS value',(Jsonb(document),)).fetchone()['value']
                    result=True
                    if expected:assert actual==normalized,label
                except Error as error:
                    assert error.sqlstate=='22023',(label,error.sqlstate)
                    result=False
            finally:owner.execute('ROLLBACK TO SAVEPOINT original_build_domain')
            accepted+=int(expected)
            if result!=expected:mismatches.append((label,expected,result))
        assert not mismatches,mismatches
        print('BUILD_CANONICAL_DOMAIN',len(cases),'accepted',accepted)
        owner.rollback()
        assert owner.execute("SELECT count(*) AS count FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)",(names,)).fetchone()['count']==0
        owner.rollback()


def test_native_original_build_json_matches_original_decoded_hash_input(native_signed_source):
    import json
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ORIGINAL_BUILD_JSON_SQL
    with isolated_owner() as owner:
        owner.execute(CAPACITY_ORIGINAL_BUILD_JSON_SQL)
        flags=owner.execute("""SELECT p.provolatile,p.proisstrict,p.prosecdef,p.proconfig,
            pg_get_userbyid(p.proowner) AS owner,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
            has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_execute,
            EXISTS(SELECT 1 FROM aclexplode(p.proacl) WHERE grantee=0 AND privilege_type='EXECUTE') AS public_execute
            FROM pg_proc p WHERE p.oid='aos_capacity_publication_private.original_build_json(jsonb)'::regprocedure""").fetchone()
        assert flags['provolatile']=='i' and flags['proisstrict'] and not flags['prosecdef']
        assert flags['owner']=='aos_capacity_publication_owner'
        assert flags['proconfig']==['search_path=pg_catalog','extra_float_digits=3']
        assert not flags['runtime_execute'] and not flags['issuer_execute'] and not flags['public_execute']
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        samples=[None,True,False,0,1,-1,1.0,-0.0,1e15,1e16,1e-4,1e-5,
                 1.2345678901234567,5e-324,1.7976931348623157e308,
                 '中文\n\t\b\f\r\\"',{'z':[1e15,1e-5,None], '中文':{'😀':1.0}}]
        samples += [float(f'1.234567890123456e{exponent}') for exponent in range(-20,25)]
        mismatches=[]
        for value in samples:
            row=owner.execute('SELECT %s::jsonb AS decoded,aos_capacity_publication_private.original_build_json(%s) AS canonical',(Jsonb(value),Jsonb(value))).fetchone()
            expected=json.dumps(row['decoded'],ensure_ascii=False,sort_keys=True,separators=(',',':'))
            if row['canonical']!=expected:mismatches.append((repr(value),expected,row['canonical']))
        # JSONB decimal scale survives; compare the original decoder, including
        # binary64 overflow/underflow, rather than the pre-insert Python value.
        for raw in ('1e-4000','-1e-4000','2e-324','-2e-324','1'+('0'*310)+'.0','-1'+('0'*310)+'.0'):
            row=owner.execute('SELECT %s::jsonb AS decoded,aos_capacity_publication_private.original_build_json(%s::jsonb) AS canonical',(raw,raw)).fetchone()
            expected=json.dumps(row['decoded'],ensure_ascii=False,sort_keys=True,separators=(',',':'))
            if row['canonical']!=expected:mismatches.append((raw[:40],expected,row['canonical']))
        assert not mismatches,mismatches
        print('BUILD_JSON_DOMAIN',len(samples)+6)
        owner.rollback()
        assert owner.execute("SELECT to_regprocedure('aos_capacity_publication_private.original_build_json(jsonb)') AS fn").fetchone()['fn'] is None
        owner.rollback()


def test_native_original_evidence_row_reads_real_verified_build(native_signed_source):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_production_contracts import ExactRevisionRef
    from aos_api.evidence_bundle_provenance import read_build_provenance
    from aos_api import aip_provider_capacity_publication_store as publication
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        row=owner.execute('SELECT bundle_id,revision,content_hash FROM public.aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s LIMIT 1',SCOPE.key).fetchone()
        ref=ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=row['bundle_id'],revision=row['revision'],content_hash=row['content_hash'])
        verified=read_build_provenance(owner,SCOPE,ref)
        assert verified.source==ref
        # The full native query must rederive all original facts, not consume
        # this Python verification result or accept a caller-provided flag.
        query=publication.CAPACITY_NATIVE_EVIDENCE_ROW_SQL
        _install_original_evidence_profile(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        actual=owner.execute(query,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id,
            'bundle_id':ref.resource_id,'revision':ref.revision,'content_hash':ref.content_hash}).fetchone()
        assert actual is not None
        assert actual['bundle_id']==ref.resource_id and actual['content_hash']==ref.content_hash
        owner.rollback()


def test_native_original_build_equality_matches_original_decoder(native_signed_source):
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    pairs=[(1,1.0),(True,1),(False,0.0),(1,2),(1.1,1),(True,'true'),
           ({'n':[1,True]}, {'n':[1.0,1]}),([1,2],[2,1]),(None,False),
           (None,None),('中文','中文'),({'a':1},{'b':1}),([],[]),({},{}),
           (9007199254740993,9007199254740992.0),(9007199254740992,9007199254740992.0)]
    with isolated_owner() as owner:
        _install_original_evidence_profile(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for left,right in pairs:
            row=owner.execute('SELECT %s::jsonb AS lhs,%s::jsonb AS rhs,aos_capacity_publication_private.original_build_equal(%s,%s) AS equal',(Jsonb(left),Jsonb(right),Jsonb(left),Jsonb(right))).fetchone()
            assert row['equal']==(row['lhs']==row['rhs']),(left,right)
        huge='1'+('0'*310)+'.0'
        raw_pairs=[('1e-4000','0.0'),('-1e-4000','false'),(huge,huge),(huge,huge[:-2]),
                   ('1.00000000000000001','true'),('9007199254740993.0','9007199254740993')]
        for left,right in raw_pairs:
            row=owner.execute('SELECT %s::jsonb AS lhs,%s::jsonb AS rhs,aos_capacity_publication_private.original_build_equal(%s::jsonb,%s::jsonb) AS equal',(left,right,left,right)).fetchone()
            assert row['equal']==(row['lhs']==row['rhs']),(left[:40],right[:40])
        print('ORIGINAL_DECODED_EQUALITY_DOMAIN',len(pairs)+len(raw_pairs))
        owner.rollback()


def _install_original_evidence_profile(owner):
    from aos_api import aip_provider_capacity_publication_store as publication
    for name in ('CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL','CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL',
                 'CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL','CAPACITY_ORIGINAL_BUILD_PROFILE_SQL',
                 'CAPACITY_ORIGINAL_BUILD_JSON_SQL','CAPACITY_ORIGINAL_EVIDENCE_PROFILE_SQL'):
        owner.execute(getattr(publication,name))


def _native_evidence_read(owner,ref):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_NATIVE_EVIDENCE_ROW_SQL
    try:
        with owner.transaction():
            return owner.execute(CAPACITY_NATIVE_EVIDENCE_ROW_SQL,dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
                bundle_id=ref.resource_id,revision=ref.revision,content_hash=ref.content_hash)).fetchone()
    except psycopg.Error as error:
        assert error.sqlstate=='22023'
        return None


def _original_evidence_read(owner,ref):
    from pydantic import ValidationError
    from aos_api.aip_production_contract_store import AipProductionContractStore,ProductionContractError
    from aos_api.evidence_bundle_provenance import read_build_provenance,BuildProvenanceUnavailable
    try:
        evidence=AipProductionContractStore().get_evidence_bundle(SCOPE,ref.resource_id,ref.revision,conn=owner)
        if evidence.content_hash!=ref.content_hash or evidence.lifecycle.value!='frozen' or evidence.revoked:return False
        return read_build_provenance(owner,SCOPE,ref).source==ref
    except (ValidationError,ProductionContractError,BuildProvenanceUnavailable):return False


def test_native_evidence_query_preserves_original_row_domains_and_faults(native_signed_source):
    import copy
    from datetime import timedelta,timezone
    from psycopg.types.json import Jsonb
    from psycopg import sql
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from tests.aip.test_evidence_bundle_provenance_pg import build_inputs,ACTOR,exact
    producer,key,body=build_inputs.__wrapped__()
    bundle=producer.build_evidence_bundle(SCOPE,ACTOR,key,body.model_copy(update=dict(license_summary={'amount':1})))
    ref=exact(bundle)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        before=owner.execute('SELECT * FROM public.aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s',(*SCOPE.key,ref.resource_id,ref.revision)).fetchone()
        original=owner.execute('SELECT * FROM public.aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s',(*SCOPE.key,ref.resource_id,ref.revision)).fetchone()
        receipt=owner.execute("SELECT * FROM public.aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.build' AND idempotency_key=%s",(*SCOPE.key,original['idempotency_key'])).fetchone()
        _install_original_evidence_profile(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert _original_evidence_read(owner,ref) and _native_evidence_read(owner,ref)
        items=copy.deepcopy(before['item_refs']);items[0]['revision']=True
        faults=[('license-float','evidence','license_summary',{'amount':1.0},True),
                ('license-boolean','evidence','license_summary',{'amount':True},True),
                ('coercive-item-revision','evidence','item_refs',items,True),
                ('receipt-coercive-revision','receipt','result_ref',{**receipt['result_ref'],'revision':True},True),
                ('license-change','evidence','license_summary',{'amount':2},False),
                ('items-change','evidence','item_refs',[],False),
                ('subject-change','evidence','subject_refs',[{'resourceType':'Subject','resourceId':'x','revision':None,'authority':'test'}],False),
                ('marking-change','evidence','marking',['changed'],False),
                ('cutoff-change','evidence','cutoff_at',before['cutoff_at']+timedelta(seconds=1),False),
                ('coverage-change','evidence','coverage','blocked' if before['coverage']!='blocked' else 'unknown',False),
                ('freshness-change','evidence','freshness','unknown' if before['freshness']!='unknown' else 'fresh',False),
                ('missing-shape','evidence','missing',['invalid'],False),
                ('request-hash','provenance','request_hash','d'*64,False),
                ('noncanonical-build','provenance','request_payload',{**original['request_payload'],'extra':True},False),
                ('source-field-drift','provenance','request_payload',{**original['request_payload'],'marking':['different']},False),
                ('authority-payload','provenance','authority_payload',{},False),
                ('idempotency-parent','provenance','idempotency_key','no-receipt-'+key,False),
                ('receipt-hash','receipt','request_hash','e'*64,False),
                ('receipt-result','receipt','result_ref',{**receipt['result_ref'],'resourceId':'other'},False)]
        tables={'evidence':'aip_evidence_bundle_revision','provenance':'aip_evidence_bundle_build_provenance','receipt':'aip_production_contract_receipt'}
        for label,target,column,value,expected in faults:
            owner.execute('RESET ROLE');owner.execute('SAVEPOINT exact_build_row_fault')
            try:
                owner.execute("SET LOCAL session_replication_role='replica'")
                predicate='receipt_id=%s' if target=='receipt' else 'bundle_id=%s AND revision=%s'
                args=(receipt['receipt_id'],) if target=='receipt' else (ref.resource_id,ref.revision)
                value=Jsonb(value) if isinstance(value,(dict,list)) else value
                rows=owner.execute(sql.SQL('UPDATE public.{} SET {}=%s WHERE org_id=%s AND project_id=%s AND '+predicate+' RETURNING 1').format(sql.Identifier(tables[target]),sql.Identifier(column)),(value,*SCOPE.key,*args)).fetchall()
                assert len(rows)==1,label
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert _original_evidence_read(owner,ref)==expected,label
                assert bool(_native_evidence_read(owner,ref))==expected,label
            finally:owner.execute('ROLLBACK TO SAVEPOINT exact_build_row_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert _original_evidence_read(owner,ref) and _native_evidence_read(owner,ref),label
        wrong=ref.model_copy(update={'content_hash':'f'*64})
        assert not _original_evidence_read(owner,wrong) and _native_evidence_read(owner,wrong) is None
        assert owner.execute('SELECT 1 FROM public.aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND bundle_id=%s',('dev-org',SCOPE.project_id,ref.resource_id)).fetchone() is None
        print('NATIVE_EVIDENCE_ROW_DOMAIN',len(faults),'single-field cases; original hash preserved for numeric positives')
        owner.rollback()


@pytest.mark.parametrize('target',['request','account','basis'])
def test_native_evidence_query_checks_three_distinct_original_source_origins(source_inputs,approved_command,private_database,target):
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from aos_api.db import connect_serializable
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_contracts import ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims,ProviderCapacityFormalBoundaryBlocked
    from aos_api.aip_production_contracts import ExactRevisionRef,RevokeEvidenceBundleRequest
    from tests.aip.test_evidence_bundle_provenance_pg import build_inputs,ACTOR
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker,checker,source,_=source_inputs
    with connect_serializable(SCOPE) as conn:
        account=ProviderPhysicalAccountCandidate.model_validate(conn.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',(source.physical_account_ref.asset_id,)).fetchone()['request_json']['candidate'])
        basis=ProviderCapacityBasisCandidate.model_validate(conn.execute('SELECT request_json FROM public.aip_provider_capacity_candidate WHERE candidate_id=%s',(source.basis_ref.asset_id,)).fetchone()['request_json']['candidate'])
    refs={'request':account.evidence_ref}
    for kind in ('account','basis'):
        producer,key,body=build_inputs.__wrapped__()
        bundle=producer.build_evidence_bundle(SCOPE,ACTOR,key,body)
        refs[kind]=account.evidence_ref.model_copy(update=dict(asset_id=bundle.bundle_id,revision=bundle.revision,content_hash=bundle.content_hash))
    assert len({ref.asset_id for ref in refs.values()})==3
    store=ProviderCapacityCandidateStore()
    saved=store.create_account(SCOPE,maker,'native-three-account-'+uuid4().hex,account.model_copy(update=dict(evidence_ref=refs['account'])))
    account_ref=source.physical_account_ref.model_copy(update=dict(asset_id=saved['candidate_id'],content_hash=saved['content_hash']))
    saved=store.create_basis(SCOPE,maker,'native-three-basis-'+uuid4().hex,basis.model_copy(update=dict(physical_account_ref=account_ref,evidence_ref=refs['basis'])))
    changed=source.model_copy(update=dict(physical_account_ref=account_ref,basis_ref=source.basis_ref.model_copy(update=dict(asset_id=saved['candidate_id'],content_hash=saved['content_hash']))))
    proposal=propose_provider_capacity_source(maker,changed,'native-three-proposal-'+uuid4().hex,changed.valid_until)
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'native-three-approval-'+uuid4().hex,DecideActionProposalRequest(
        expectedProposalVersion=proposal.proposal.version,expectedProposalHash=proposal.proposal.proposal_hash,
        decision='approved',reason='isolated native original three Evidence origins',approvalExpiresAt=changed.valid_until))
    command=approved_command[-1].model_copy(update=dict(idempotency_key='native-three-private-'+uuid4().hex,
        approved_proposal=approved_command[-1].approved_proposal.model_copy(update=dict(asset_id=approved.proposal.id,
            revision=approved.proposal.version,content_hash=approved.proposal.proposal_hash)),
        approval_event=approved_command[-1].approval_event.model_copy(update=dict(asset_id=approved.approvals[0].id,
            content_hash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True))))))
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        fact=read_capacity_approved_claims(conn,command)
        assert conn.pgconn.used_password is True
        assert fact.source==changed and not fact.execution_allowed and not fact.supplier_verified
    exacts={key:ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=ref.asset_id,
        revision=ref.revision,content_hash=ref.content_hash) for key,ref in refs.items()}
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        _install_original_evidence_profile(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert all(_native_evidence_read(owner,ref) and _original_evidence_read(owner,ref) for ref in exacts.values())
        ref=exacts[target]
        parent=owner.execute('SELECT idempotency_key FROM public.aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s',(*SCOPE.key,ref.resource_id,ref.revision)).fetchone()
        for table in ('aip_production_contract_receipt','aip_evidence_bundle_build_provenance'):
            owner.execute('RESET ROLE');owner.execute('SAVEPOINT three_origin_hash_fault')
            try:
                owner.execute("SET LOCAL session_replication_role='replica'")
                predicate="operation='evidence_bundle.build' AND idempotency_key=%s" if table.endswith('receipt') else 'bundle_id=%s AND revision=%s'
                args=(parent['idempotency_key'],) if table.endswith('receipt') else (ref.resource_id,ref.revision)
                rows=owner.execute(psycopg.sql.SQL('UPDATE public.{} SET request_hash=%s WHERE org_id=%s AND project_id=%s AND '+predicate+' RETURNING 1').format(psycopg.sql.Identifier(table)),('d'*64,*SCOPE.key,*args)).fetchall()
                assert len(rows)==1
                owner.execute("SET LOCAL session_replication_role='origin'");owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                for key,item in exacts.items():
                    assert bool(_native_evidence_read(owner,item))==(key!=target),(key,table)
                    assert _original_evidence_read(owner,item)==(key!=target),(key,table)
            finally:owner.execute('ROLLBACK TO SAVEPOINT three_origin_hash_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert all(_native_evidence_read(owner,item) for item in exacts.values())
        owner.rollback()
    # A genuine committed revoke runs the original runtime and epoch triggers;
    # its outcome is observed independently through actual SCRAM claims.
    producer.revoke_evidence_bundle(SCOPE,ACTOR,ref.resource_id,'native-three-revoke-'+uuid4().hex,
        RevokeEvidenceBundleRequest(expectedRevision=ref.revision,expectedContentHash=ref.content_hash,reason='isolated genuine original origin revoke'))
    with connect_capacity_issuer(private_database,SCOPE) as conn:
        assert conn.pgconn.used_password is True
        with pytest.raises(ProviderCapacityFormalBoundaryBlocked):read_capacity_approved_claims(conn,command)
        conn.rollback()
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        _install_original_evidence_profile(owner);owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for key,item in exacts.items():
            assert bool(_native_evidence_read(owner,item))==(key!=target)
            assert _original_evidence_read(owner,item)==(key!=target)
        print('NATIVE_THREE_DISTINCT_EVIDENCE',target,'database',owner.info.dbname,'distinct',len(exacts),'original_scram_positive_then_genuine_revoke_refused')
        owner.rollback()


def test_native_evidence_contract_rejects_coherently_rehashed_bad_metadata(native_signed_source):
    from psycopg.types.json import Jsonb
    from psycopg import sql
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_production_contract_store import canonical_hash
    from aos_api.aip_production_contracts import ExactRevisionRef
    from aos_api.evidence_bundle_provenance import read_build_provenance
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        row=owner.execute('SELECT e.*,p.request_payload,p.idempotency_key FROM public.aip_evidence_bundle_revision e JOIN public.aip_evidence_bundle_build_provenance p USING(org_id,project_id,bundle_id,revision,content_hash) WHERE e.org_id=%s AND e.project_id=%s LIMIT 1',SCOPE.key).fetchone()
        _install_original_evidence_profile(owner)
        names=['original_build_float','original_build_equal','original_evidence_fields']
        flags=owner.execute("""SELECT p.provolatile,p.proisstrict,p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
            has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_execute,
            EXISTS(SELECT 1 FROM aclexplode(p.proacl) WHERE grantee=0 AND privilege_type='EXECUTE') AS public_execute
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)""",(names,)).fetchall()
        assert len(flags)==3
        assert all(f['provolatile']=='i' and f['proisstrict'] and not f['prosecdef'] and f['proconfig']==['search_path=pg_catalog']
            and f['owner']=='aos_capacity_publication_owner' and not f['runtime_execute'] and not f['issuer_execute'] and not f['public_execute'] for f in flags)
        for field in ('missing','conflicts','uncertainties'):
            owner.execute('SAVEPOINT coherent_evidence_model_fault')
            try:
                payload={**row['request_payload'],**{name:row[name] for name in ('coverage','missing','conflicts','uncertainties','freshness')}}
                payload[field]=['invalid-dictionary']
                hash_value=canonical_hash(payload)
                ref=ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=row['bundle_id'],revision=row['revision'],content_hash=hash_value)
                owner.execute("SET LOCAL session_replication_role='replica'")
                owner.execute(sql.SQL('UPDATE public.aip_evidence_bundle_revision SET {}=%s,content_hash=%s WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s').format(sql.Identifier(field)),(Jsonb(payload[field]),hash_value,*SCOPE.key,ref.resource_id,ref.revision))
                owner.execute('UPDATE public.aip_evidence_bundle_build_provenance SET content_hash=%s,authority_payload=%s WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s',(hash_value,Jsonb(payload),*SCOPE.key,ref.resource_id,ref.revision))
                owner.execute("UPDATE public.aip_production_contract_receipt SET result_ref=%s WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.build' AND idempotency_key=%s",(Jsonb(ref.model_dump(mode='json',by_alias=True)),*SCOPE.key,row['idempotency_key']))
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert read_build_provenance(owner,SCOPE,ref).source==ref
                assert not _original_evidence_read(owner,ref),field
                assert _native_evidence_read(owner,ref) is None,field
            finally:owner.execute('ROLLBACK TO SAVEPOINT coherent_evidence_model_fault')
        owner.rollback()
        assert owner.execute("SELECT count(*) AS count FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_capacity_publication_private' AND p.proname=ANY(%s)",(names,)).fetchone()['count']==0
        owner.rollback()


@pytest.mark.parametrize('offset',[None,1439])
def test_native_evidence_query_preserves_genuine_build_cutoff_and_numeric_hash(native_signed_source,offset):
    from datetime import timedelta,timezone
    from tests.aip.test_evidence_bundle_provenance_pg import build_inputs,ACTOR,exact
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_NATIVE_EVIDENCE_ROW_SQL
    producer,key,body=build_inputs.__wrapped__()
    cutoff=body.cutoff_at.replace(tzinfo=None) if offset is None else body.cutoff_at.astimezone(timezone(timedelta(minutes=offset)))
    bundle=producer.build_evidence_bundle(SCOPE,ACTOR,key,body.model_copy(update=dict(cutoff_at=cutoff,
        license_summary={'nested':[1e15,1e-5,1.2345678901234567,True,None]})))
    ref=exact(bundle)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        _install_original_evidence_profile(owner);owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        assert _original_evidence_read(owner,ref) and _native_evidence_read(owner,ref)
        params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,bundle_id=ref.resource_id,revision=ref.revision,content_hash=ref.content_hash)
        for field,value in [('org_id','dev-org'),('project_id','other'),('bundle_id','missing'),('revision',ref.revision+1),('content_hash','f'*64)]:
            assert owner.execute(CAPACITY_NATIVE_EVIDENCE_ROW_SQL,{**params,field:value}).fetchone() is None
        owner.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert owner.execute(CAPACITY_NATIVE_EVIDENCE_ROW_SQL,params).fetchone() is None
        owner.execute("SELECT set_config('aos.org_id',%s,true)",(SCOPE.org_id,))
        assert _native_evidence_read(owner,ref)
        print('NATIVE_EVIDENCE_CUTOFF',offset,'actual_original_build_hash_and_utc_match')
        owner.rollback()


def _install_original_withdrawal_audit(owner):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL
    owner.execute(CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL)


def _assert_native_withdrawal_rejects(owner,reason):
    with pytest.raises(psycopg.errors.InvalidParameterValue) as captured:
        with owner.transaction():
            owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
    assert captured.value.diag.message_primary==reason


@pytest.mark.parametrize('statement,reason',[
    ('ALTER ROLE aos_capacity_withdrawal_epoch_owner LOGIN','WITHDRAWAL_OWNER_DRIFT'),
    ('ALTER ROLE aos_capacity_withdrawal_epoch_owner INHERIT','WITHDRAWAL_OWNER_DRIFT'),
    ('ALTER TABLE public.aip_capacity_withdrawal_epoch DISABLE ROW LEVEL SECURITY','WITHDRAWAL_TABLE_DRIFT'),
    ('ALTER TABLE public.aip_capacity_withdrawal_epoch NO FORCE ROW LEVEL SECURITY','WITHDRAWAL_TABLE_DRIFT'),
    ('GRANT SELECT ON public.aip_capacity_withdrawal_epoch TO aos_runtime','WITHDRAWAL_TABLE_ACL_DRIFT'),
    ('GRANT SELECT(epoch) ON public.aip_capacity_withdrawal_epoch TO aos_runtime','WITHDRAWAL_TABLE_ACL_DRIFT'),
    ('ALTER TABLE public.aip_capacity_withdrawal_epoch ALTER COLUMN epoch SET DEFAULT 1','WITHDRAWAL_TABLE_STRUCTURE_DRIFT'),
    ('ALTER TABLE public.aip_capacity_withdrawal_epoch ADD CONSTRAINT isolated_extra_check CHECK (true)','WITHDRAWAL_TABLE_STRUCTURE_DRIFT'),
    ('ALTER POLICY capacity_withdrawal_epoch_scope ON public.aip_capacity_withdrawal_epoch USING (true)','WITHDRAWAL_POLICY_DRIFT'),
    ('ALTER FUNCTION public.aos_capacity_withdrawal_epoch_init() SECURITY INVOKER','WITHDRAWAL_FUNCTION_DRIFT'),
    ("CREATE OR REPLACE FUNCTION public.aos_capacity_withdrawal_epoch_bump() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$",'WITHDRAWAL_FUNCTION_DRIFT'),
    ('GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_init() TO aos_runtime','WITHDRAWAL_FUNCTION_ACL_DRIFT'),
    ('ALTER TABLE public.aip_action_proposal DISABLE TRIGGER zz_capacity_withdrawal_epoch_init_a0v151','WITHDRAWAL_TRIGGER_DRIFT'),
    ('ALTER TABLE public.aip_action_withdrawal_event DISABLE TRIGGER zz_capacity_withdrawal_epoch_bump_a0v151','WITHDRAWAL_TRIGGER_DRIFT'),
])
def test_original_withdrawal_catalog_fault_oracle(native_signed_source,statement,reason):
    """Exact original rejection contract for future native157; no native entry claim."""
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence,CapacityWithdrawalFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_withdrawal_fence(owner)
        owner.execute('SAVEPOINT withdrawal_catalog_fault')
        try:
            owner.execute(statement)
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            with pytest.raises(CapacityWithdrawalFenceBlocked,match='^'+reason+'$'):
                require_withdrawal_fence(owner)
            _assert_native_withdrawal_rejects(owner,reason)
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT withdrawal_catalog_fault')
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        owner.rollback()
    print('ORIGINAL_WITHDRAWAL_FAULT_RESTORED',reason,statement)


def test_original_withdrawal_catalog_rejects_extra_neutral_owner_function(native_signed_source):
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence,CapacityWithdrawalFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_withdrawal_fence(owner)
        owner.execute('SAVEPOINT withdrawal_extra_function')
        try:
            owner.execute("CREATE FUNCTION public.isolated_withdrawal_extra() RETURNS bigint LANGUAGE sql SET search_path=pg_catalog AS 'SELECT 0::bigint'")
            owner.execute('REVOKE EXECUTE ON FUNCTION public.isolated_withdrawal_extra() FROM PUBLIC')
            owner.execute('ALTER FUNCTION public.isolated_withdrawal_extra() OWNER TO aos_capacity_withdrawal_epoch_owner')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            with pytest.raises(CapacityWithdrawalFenceBlocked,match='^WITHDRAWAL_OWNER_EXTRA_PERMISSION$'):
                require_withdrawal_fence(owner)
            _assert_native_withdrawal_rejects(owner,'WITHDRAWAL_OWNER_EXTRA_PERMISSION')
        finally:
            owner.execute('ROLLBACK TO SAVEPOINT withdrawal_extra_function')
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        assert owner.execute("SELECT to_regprocedure('public.isolated_withdrawal_extra()') AS fn").fetchone()['fn'] is None
        owner.rollback()


def test_native_original_withdrawal_boundary_requires_implemented_audit(native_signed_source):
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for name in ('require_original_fact_boundary','require_original_epoch_pair_boundary','require_original_withdrawal_boundary'):
            owner.execute('SELECT aos_capacity_publication_private.'+name+'()')
        owner.execute('RESET ROLE')
        names=['require_original_fact_boundary','require_original_epoch_pair_boundary','require_original_withdrawal_boundary']
        rows=owner.execute("""SELECT p.provolatile,p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner,
         has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
         has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE') AS issuer_execute,
         EXISTS(SELECT 1 FROM aclexplode(p.proacl) WHERE grantee=0) AS public_grant
         FROM pg_proc p WHERE p.pronamespace='aos_capacity_publication_private'::regnamespace AND p.proname=ANY(%s)""",(names,)).fetchall()
        assert len(rows)==3 and all(r['provolatile']=='v' and not r['prosecdef'] and r['proconfig']==['search_path=pg_catalog']
            and r['owner']=='aos_capacity_publication_owner' and not r['runtime_execute'] and not r['issuer_execute'] and not r['public_grant'] for r in rows)
        owner.rollback()
        assert owner.execute("SELECT count(*) AS n FROM pg_proc WHERE pronamespace='aos_capacity_publication_private'::regnamespace AND proname=ANY(%s)",(names,)).fetchone()['n']==0
        owner.rollback()


@pytest.mark.parametrize('statement',[
    'REVOKE EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) FROM aos_capacity_publication_owner',
    'REVOKE EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) FROM aos_capacity_publication_owner',
    'GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) TO aos_capacity_publication_owner WITH GRANT OPTION',
    'GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) TO aos_capacity_publication_owner WITH GRANT OPTION',
    'GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) TO PUBLIC',
    'GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) TO PUBLIC',
    "CREATE OR REPLACE FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(p_org text,p_project text,p_id text) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN RETURN 0; END $$",
    'ALTER FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) SECURITY INVOKER',
])
def test_native_withdrawal_audit_checks_complete_original_epoch_pair(native_signed_source,statement):
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence,CapacityWithdrawalFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_withdrawal_fence(owner)
        owner.execute('SAVEPOINT epoch_pair_native_fault')
        try:
            owner.execute(statement)
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            with pytest.raises(CapacityWithdrawalFenceBlocked,match='^WITHDRAWAL_PUBLICATION_CALLER_DRIFT$'):
                require_withdrawal_fence(owner)
            _assert_native_withdrawal_rejects(owner,'WITHDRAWAL_PUBLICATION_CALLER_DRIFT')
        finally:owner.execute('ROLLBACK TO SAVEPOINT epoch_pair_native_fault')
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        owner.rollback()


@pytest.mark.parametrize('public',[False,True])
def test_native_withdrawal_audit_rejects_effective_foreign_definer(native_signed_source,public):
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence,CapacityWithdrawalFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        owner.execute('SAVEPOINT foreign_definer_native_fault')
        try:
            owner.execute("CREATE FUNCTION public.isolated_original_epoch_foreign_definer() RETURNS bigint LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT 0::bigint'")
            if not public:
                owner.execute('REVOKE EXECUTE ON FUNCTION public.isolated_original_epoch_foreign_definer() FROM PUBLIC')
                owner.execute('GRANT EXECUTE ON FUNCTION public.isolated_original_epoch_foreign_definer() TO aos_capacity_publication_owner')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            with pytest.raises(CapacityWithdrawalFenceBlocked,match='^WITHDRAWAL_PUBLICATION_CALLER_DRIFT$'):
                require_withdrawal_fence(owner)
            _assert_native_withdrawal_rejects(owner,'WITHDRAWAL_PUBLICATION_CALLER_DRIFT')
        finally:owner.execute('ROLLBACK TO SAVEPOINT foreign_definer_native_fault')
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        owner.rollback()


@pytest.mark.parametrize('statement,reason',[
    ('GRANT aos_runtime TO aos_capacity_withdrawal_epoch_owner','WITHDRAWAL_OWNER_DRIFT'),
    ('ALTER TABLE public.aip_capacity_withdrawal_epoch OWNER TO aos_runtime','WITHDRAWAL_TABLE_DRIFT'),
    ('ALTER TABLE public.aip_capacity_withdrawal_epoch ADD COLUMN unexpected text','WITHDRAWAL_TABLE_STRUCTURE_DRIFT'),
    ('CREATE POLICY isolated_extra ON public.aip_capacity_withdrawal_epoch USING(true)','WITHDRAWAL_POLICY_DRIFT'),
    ('ALTER POLICY capacity_withdrawal_epoch_scope ON public.aip_capacity_withdrawal_epoch TO aos_runtime','WITHDRAWAL_POLICY_DRIFT'),
    ('ALTER FUNCTION public.aos_capacity_withdrawal_epoch_init() SET search_path=public','WITHDRAWAL_FUNCTION_DRIFT'),
    ('GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_bump() TO PUBLIC','WITHDRAWAL_PUBLICATION_CALLER_DRIFT'),
    ('GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_init() TO aos_capacity_withdrawal_epoch_owner WITH GRANT OPTION','WITHDRAWAL_FUNCTION_ACL_DRIFT'),
    ('GRANT USAGE ON SCHEMA public TO aos_capacity_withdrawal_epoch_owner WITH GRANT OPTION','WITHDRAWAL_OWNER_EXTRA_PERMISSION'),
])
def test_native_original_withdrawal_extended_catalog_faults(native_signed_source,statement,reason):
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence,CapacityWithdrawalFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_withdrawal_fence(owner)
        owner.execute('SAVEPOINT withdrawal_extended_fault')
        try:
            owner.execute(statement)
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            with pytest.raises(CapacityWithdrawalFenceBlocked,match='^'+reason+'$'):
                require_withdrawal_fence(owner)
            _assert_native_withdrawal_rejects(owner,reason)
        finally:owner.execute('ROLLBACK TO SAVEPOINT withdrawal_extended_fault')
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        owner.rollback()


@pytest.mark.parametrize('fault',['disabled_fk','deferred_fk','extra_owned_table','unvalidated_check','legacy_no_pair'])
def test_native_original_withdrawal_structural_and_legacy_controls(native_signed_source,fault):
    from psycopg import sql
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence,CapacityWithdrawalFenceBlocked
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        require_withdrawal_fence(owner)
        owner.execute('SAVEPOINT withdrawal_structure_fault')
        try:
            reason='WITHDRAWAL_FOREIGN_KEY_ORDER_DRIFT'
            if fault=='disabled_fk':
                fk=owner.execute("SELECT tgname FROM pg_trigger WHERE tgrelid='public.aip_action_withdrawal_event'::regclass AND tgisinternal AND (tgtype & 4)=4 ORDER BY tgname LIMIT 1").fetchone()['tgname']
                owner.execute(sql.SQL('ALTER TABLE public.aip_action_withdrawal_event DISABLE TRIGGER {}').format(sql.Identifier(fk)))
            elif fault=='deferred_fk':
                fk=owner.execute("SELECT conname FROM pg_constraint WHERE conrelid='public.aip_action_withdrawal_event'::regclass AND contype='f' ORDER BY conname LIMIT 1").fetchone()['conname']
                owner.execute(sql.SQL('ALTER TABLE public.aip_action_withdrawal_event ALTER CONSTRAINT {} DEFERRABLE INITIALLY DEFERRED').format(sql.Identifier(fk)))
            elif fault=='extra_owned_table':
                owner.execute('CREATE TABLE public.isolated_withdrawal_extra_owned (id text)')
                owner.execute('ALTER TABLE public.isolated_withdrawal_extra_owned OWNER TO aos_capacity_withdrawal_epoch_owner')
                reason='WITHDRAWAL_OWNER_EXTRA_PERMISSION'
            elif fault=='unvalidated_check':
                check=owner.execute("SELECT conname FROM pg_constraint WHERE conrelid='public.aip_capacity_withdrawal_epoch'::regclass AND pg_get_constraintdef(oid,true)='CHECK (epoch >= 0)'").fetchone()['conname']
                owner.execute(sql.SQL('ALTER TABLE public.aip_capacity_withdrawal_epoch DROP CONSTRAINT {}').format(sql.Identifier(check)))
                owner.execute(sql.SQL('ALTER TABLE public.aip_capacity_withdrawal_epoch ADD CONSTRAINT {} CHECK(epoch>=0) NOT VALID').format(sql.Identifier(check)))
                reason='WITHDRAWAL_TABLE_STRUCTURE_DRIFT'
            else:
                owner.execute('REVOKE EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) FROM aos_capacity_publication_owner')
                owner.execute('REVOKE EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) FROM aos_capacity_publication_owner')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            if fault=='legacy_no_pair':
                require_withdrawal_fence(owner)
                owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
            else:
                with pytest.raises(CapacityWithdrawalFenceBlocked,match='^'+reason+'$'):
                    require_withdrawal_fence(owner)
                _assert_native_withdrawal_rejects(owner,reason)
        finally:owner.execute('ROLLBACK TO SAVEPOINT withdrawal_structure_fault')
        require_withdrawal_fence(owner)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        owner.execute('SELECT aos_capacity_publication_private.require_original_withdrawal_boundary()')
        owner.rollback()


@pytest.mark.parametrize('role',['aos_runtime','aos_provider_capacity_issuer'])
def test_native_original_withdrawal_audit_denied_to_ordinary_callers(native_signed_source,role):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        _install_original_withdrawal_audit(owner)
        owner.execute('SET LOCAL ROLE '+role)
        for name in ('require_original_fact_boundary','require_original_epoch_pair_boundary','require_original_withdrawal_boundary'):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with owner.transaction():
                    owner.execute('SELECT aos_capacity_publication_private.'+name+'()')
        owner.rollback()


def test_native_registered_signed_document_current_rows_require_exact_originals(native_signed_source,tmp_path):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs
    from aos_api import aip_provider_capacity_publication_store as native
    material=_registered_publication_inputs(native_signed_source,tmp_path)
    command,policy,attestation=material['actual_command']()
    with connect_capacity_issuer(material['config'],SCOPE) as issuer:
        assert issuer.pgconn.used_password
        original=check_native_capacity_supplier_inputs(issuer,command,policy,attestation,trust_roots=material['provider'])
        assert original.execution_allowed is False
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for ref,(raw,signature) in zip(material['refs'],material['documents']):
            params=dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,kind=ref['assetType'],
                asset_id=ref['assetId'],revision=str(ref['revision']),content_hash=ref['contentHash'])
            row=owner.execute(native.CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,params).fetchone()
            assert row is not None and bytes(row['raw_body'])==raw and bytes(row['signature'])==signature
            assert row['origin_hash']==material['origin_hash'] and row['snapshot_hash']==material['snapshot_hash']
        owner.rollback()
    print('NATIVE_REGISTERED_ORIGINAL_SIGNED_DOCUMENTS three_exact_rows original_scram_positive no_source_publication')


def _current_signed_params(ref):
    return dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,kind=ref['assetType'],
        asset_id=ref['assetId'],revision=str(ref['revision']),content_hash=ref['contentHash'])


def _read_native_current_signed(owner,params):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL
    try:
        with owner.transaction():
            return owner.execute(CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,params).fetchone()
    except psycopg.Error as error:
        assert error.sqlstate in ('22023','22P02','22003'),error.sqlstate
        return None


def test_native_current_signed_document_single_field_faults_restore_exact_originals(native_signed_source,tmp_path):
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.asset_registry.canonical_json import canonical_json
    from psycopg.types.json import Jsonb
    material=_registered_publication_inputs(native_signed_source,tmp_path)
    ref=material['refs'][1];params=_current_signed_params(ref)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        original=_read_native_current_signed(owner,params);assert original
        owner.execute('RESET ROLE')
        document_where=' WHERE org_id=%s AND project_id=%s AND content_hash=%s'
        root_where=' WHERE org_id=%s AND project_id=%s AND snapshot_hash=%s AND root_ordinal=%s'
        dargs=(*SCOPE.key,ref['contentHash']);rargs=(*SCOPE.key,original['snapshot_hash'],original['root_ordinal'])
        faults={
            'signature':('UPDATE aos_capacity_publication_private.document SET signature=%s'+document_where,(Ed25519PrivateKey.generate().sign(bytes(original['raw_body'])),*dargs)),
            'raw_canonical':('UPDATE aos_capacity_publication_private.document SET raw_body=%s,content_hash=%s'+document_where,(bytes(original['raw_body'])+b' ',hashlib.sha256(bytes(original['raw_body'])+b' ').hexdigest(),*dargs)),
            'identity_hash':('UPDATE aos_capacity_publication_private.document SET identity_hash=%s'+document_where,('0'*64,*dargs)),
            'document_origin':('UPDATE aos_capacity_publication_private.document SET origin_hash=%s'+document_where,('0'*64,*dargs)),
            'document_snapshot':('UPDATE aos_capacity_publication_private.document SET snapshot_hash=%s'+document_where,('sha256:'+'0'*64,*dargs)),
            'document_root_ordinal':('UPDATE aos_capacity_publication_private.document SET root_ordinal=%s'+document_where,(9999,*dargs)),
            'registry_epoch':('UPDATE aos_capacity_publication_private.registry_epoch SET epoch=epoch+1 WHERE org_id=%s AND project_id=%s',SCOPE.key),
            'registry_head':('UPDATE aos_capacity_publication_private.registry_epoch SET head_origin_hash=NULL WHERE org_id=%s AND project_id=%s',SCOPE.key),
            'root_public_key':('UPDATE aos_capacity_publication_private.root_entry SET public_key=%s'+root_where,(b'\x00'*32,*rargs)),
            'root_revision':('UPDATE aos_capacity_publication_private.root_entry SET root_revision=%s'+root_where,('sha256:'+'0'*64,*rargs)),
            'root_expiry':("UPDATE aos_capacity_publication_private.root_entry SET not_after=clock_timestamp()-interval '1 second'"+root_where,rargs),
            'root_future':("UPDATE aos_capacity_publication_private.root_entry SET not_before=clock_timestamp()+interval '1 minute'"+root_where,rargs),
            'root_revoked':("UPDATE aos_capacity_publication_private.root_entry SET revoked_at=clock_timestamp()-interval '1 second'"+root_where,rargs),
            'root_canonical':('UPDATE aos_capacity_publication_private.root_entry SET canonical_root=canonical_root||%s'+root_where,(b' ',*rargs)),
            'root_publisher_points':('UPDATE aos_capacity_publication_private.root_entry SET publisher_codepoints=%s,publisher_literal=%s'+root_where,([ord(c) for c in 'different-publisher'],'"different-publisher"',*rargs)),
            'snapshot_count':('UPDATE aos_capacity_publication_private.root_snapshot SET root_count=root_count+1 WHERE org_id=%s AND project_id=%s AND snapshot_hash=%s',(*SCOPE.key,original['snapshot_hash'])),
            'snapshot_raw':('UPDATE aos_capacity_publication_private.root_snapshot SET raw_body=raw_body||%s WHERE org_id=%s AND project_id=%s AND snapshot_hash=%s',(b' ',*SCOPE.key,original['snapshot_hash'])),
            'origin_signature':('UPDATE aos_capacity_publication_private.origin SET signature=%s WHERE org_id=%s AND project_id=%s AND content_hash=%s',(b'\x00'*64,*SCOPE.key,original['origin_hash'])),
            'anchor_subject':('UPDATE aos_capacity_publication_private.deployment_anchor SET publisher_subject=%s WHERE org_id=%s AND project_id=%s AND anchor_revision=%s',('different-subject',*SCOPE.key,original['anchor_revision'])),
            'anchor_key':('UPDATE aos_capacity_publication_private.deployment_anchor SET signer_public_key=%s WHERE org_id=%s AND project_id=%s AND anchor_revision=%s',(b'\x00'*32,*SCOPE.key,original['anchor_revision'])),
            'verifier_mode':('ALTER FUNCTION aos_ed25519.verify(bytea,bytea,bytea) STABLE',None),
            'verifier_strict':('ALTER FUNCTION aos_ed25519.verify(bytea,bytea,bytea) CALLED ON NULL INPUT',None),
        }
        # Replica bypasses triggers/FKs, never CHECK constraints. Those two
        # rejected corruptions prove storage enforcement, not query behavior.
        for name,(statement,args) in faults.items():
            owner.execute('SAVEPOINT current_signed_fault')
            try:
                owner.execute("SET LOCAL session_replication_role='replica'")
                if name in ('identity_hash','snapshot_raw'):
                    with pytest.raises(psycopg.errors.CheckViolation):
                        owner.execute(statement,args)
                else:
                    owner.execute(statement,args)
                    owner.execute("SET LOCAL session_replication_role='origin'")
                    owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                    actual = dict(params)
                    if name == 'raw_canonical':
                        actual['content_hash'] = hashlib.sha256(bytes(original['raw_body'])+b' ').hexdigest()
                    assert _read_native_current_signed(owner,actual) is None,name
            finally:owner.execute('ROLLBACK TO SAVEPOINT current_signed_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert _read_native_current_signed(owner,params),name
            owner.execute('RESET ROLE')
        # Exact row identity can be made internally coherent while disagreeing
        # with its signed payload. Compare with the matching altered row params.
        for field,value in [('asset_id','coherent-different-id'),('revision','2')]:
            owner.execute('SAVEPOINT current_signed_identity_fault')
            try:
                actual={**params,field:value}
                identity=hashlib.sha256(b'aos-capacity-document-identity/v1\0'+actual['kind'].encode()+b'\0'+actual['asset_id'].encode()+b'\0'+actual['revision'].encode()).hexdigest()
                from psycopg import sql
                owner.execute("SET LOCAL session_replication_role='replica'")
                owner.execute(sql.SQL('UPDATE aos_capacity_publication_private.document SET {}=%s,identity_hash=%s'+document_where).format(sql.Identifier(field)),(value,identity,*dargs))
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert _read_native_current_signed(owner,actual) is None,field
            finally:owner.execute('ROLLBACK TO SAVEPOINT current_signed_identity_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner');assert _read_native_current_signed(owner,params)
            owner.execute('RESET ROLE')
        # Re-sign a complete original bootstrap with the controlled test anchor;
        # bind every persisted parent to it, so only actual deployment identity
        # (not a mismatched hash/signature/allowlist/policy target) rejects.
        for field in ('databaseOid','clusterIdentifier'):
            owner.execute('SAVEPOINT current_signed_deployment_fault')
            try:
                payload={**material['origin_payload'],'deploymentTarget':dict(material['origin_payload']['deploymentTarget'])}
                target=payload['deploymentTarget'];target[field]=target[field]+1 if field=='databaseOid' else str(int(target[field])+1)
                raw=canonical_json(payload);digest=hashlib.sha256(raw).hexdigest();signature=material['anchor_key'].sign(raw)
                owner.execute("SET LOCAL session_replication_role='replica'")
                owner.execute('UPDATE aos_capacity_publication_private.deployment_anchor SET deployment_target=%s WHERE org_id=%s AND project_id=%s AND anchor_revision=%s',(Jsonb(target),*SCOPE.key,original['anchor_revision']))
                owner.execute('UPDATE aos_capacity_publication_private.origin SET raw_body=%s,signature=%s,content_hash=%s WHERE org_id=%s AND project_id=%s AND content_hash=%s',(raw,signature,digest,*SCOPE.key,original['origin_hash']))
                owner.execute('UPDATE aos_capacity_publication_private.document SET origin_hash=%s WHERE org_id=%s AND project_id=%s',(digest,*SCOPE.key))
                owner.execute('UPDATE aos_capacity_publication_private.registry_epoch SET head_origin_hash=%s WHERE org_id=%s AND project_id=%s',(digest,*SCOPE.key))
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert _read_native_current_signed(owner,params) is None,field
            finally:owner.execute('ROLLBACK TO SAVEPOINT current_signed_deployment_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner');assert _read_native_current_signed(owner,params)
            owner.execute('RESET ROLE')
        owner.rollback()
    print('NATIVE_CURRENT_SIGNED_FAULTS 20_query_refusals 2_storage_CHECK_refusals 2_coherent_identity 2_resigned_deployment all_restore')


def test_native_current_signed_exact_scope_matrix_and_ordinary_role_denial(native_signed_source,tmp_path):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL
    material=_registered_publication_inputs(native_signed_source,tmp_path)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for ref in material['refs']:
            params=_current_signed_params(ref);assert _read_native_current_signed(owner,params)
            for field,value in [('org_id','dev-org'),('project_id','other'),('kind','OtherKind'),('asset_id','missing'),('revision','2'),('content_hash','0'*64)]:
                assert _read_native_current_signed(owner,{**params,field:value}) is None,(ref['assetType'],field)
            owner.execute("SELECT set_config('aos.org_id','dev-org',true)");assert _read_native_current_signed(owner,params) is None
            owner.execute("SELECT set_config('aos.org_id',%s,true)",(SCOPE.org_id,))
        for role in ('aos_runtime','aos_provider_capacity_issuer'):
            owner.execute('SET LOCAL ROLE '+role)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with owner.transaction():owner.execute(CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,_current_signed_params(material['refs'][0]))
        owner.rollback()


def _integrated_signed_origin_withdrawal(material):
    import hashlib
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_provider_capacity_withdrawal_contracts import ProviderCapacityOriginWithdrawal
    origin=material['origin_payload']
    payload=dict(schemaVersion=1,tenant=origin['tenant'],assetId='integrated-withdrawal-'+uuid4().hex,
        revision=1,publisher=origin['publisher'],keyId=origin['keyId'],
        validFrom=datetime.now(UTC)-timedelta(minutes=1),validUntil=datetime.now(UTC)+timedelta(minutes=10),
        deploymentTarget=origin['deploymentTarget'],purpose='provider_capacity_origin_withdrawal',
        anchorRevision=origin['anchorRevision'],publisherSubject=origin['publisherSubject'],
        policyPublisherRole=origin['policyPublisherRole'],originRef=dict(
            assetType='ProviderCapacityOriginBootstrapRevision',assetId=origin['assetId'],
            revision=origin['revision'],contentHash=material['origin_hash']),expectedEpoch=1)
    raw=canonical_json(ProviderCapacityOriginWithdrawal.model_validate(payload).model_dump(mode='json',by_alias=True))
    return raw,material['anchor_key'].sign(raw),hashlib.sha256(raw).hexdigest()


def _assert_integrated_signed_history(owner,material,withdrawal_count):
    assert owner.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.origin_withdrawal').fetchone()['n']==withdrawal_count
    assert owner.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.origin').fetchone()['n']==1
    rows=owner.execute('SELECT content_hash,raw_body,signature FROM aos_capacity_publication_private.document').fetchall()
    assert len(rows)==3
    actual={r['content_hash']:(bytes(r['raw_body']),bytes(r['signature'])) for r in rows}
    for ref,document in zip(material['refs'],material['documents']):
        assert actual[ref['contentHash']]==document


def test_native_current_signed_actual_withdrawal_commit_rollback_and_replay(native_signed_source,tmp_path):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    material=_registered_publication_inputs(native_signed_source,tmp_path)
    raw,signature,digest=_integrated_signed_origin_withdrawal(material)
    call='SELECT aos_capacity_publication_private.withdraw_origin(%s,%s) AS digest'
    with isolated_owner() as publisher:
        publisher.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",SCOPE.key)
        publisher.execute('SET SESSION AUTHORIZATION aos_provider_capacity_policy_publisher')
        publisher.commit()
        assert publisher.execute(call,(raw,signature)).fetchone()['digest']==digest
        publisher.rollback()
        with isolated_owner() as owner:
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            for ref in material['refs']:assert _read_native_current_signed(owner,_current_signed_params(ref))
            assert owner.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchone()==dict(epoch=1,head_origin_hash=material['origin_hash'])
            _assert_integrated_signed_history(owner,material,0)
            owner.rollback()
        assert publisher.execute(call,(raw,signature)).fetchone()['digest']==digest
        publisher.commit()
        assert publisher.execute(call,(raw,signature)).fetchone()['digest']==digest
        publisher.commit()
        publisher.execute('RESET SESSION AUTHORIZATION');publisher.commit()
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for ref in material['refs']:assert _read_native_current_signed(owner,_current_signed_params(ref)) is None
        assert owner.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchone()==dict(epoch=2,head_origin_hash=None)
        row=owner.execute('SELECT raw_body,signature,prior_epoch,new_epoch FROM aos_capacity_publication_private.origin_withdrawal').fetchone()
        assert bytes(row['raw_body'])==raw and bytes(row['signature'])==signature
        assert row['prior_epoch']==1 and row['new_epoch']==2
        _assert_integrated_signed_history(owner,material,1)
        owner.rollback()
    print('NATIVE_CURRENT_SIGNED_REAL_WITHDRAWAL rollback=all3_current commit=all3_denied replay=single history=exact')


@pytest.mark.parametrize('order',['reader_first','withdrawal_first','withdrawal_rollback_first'])
def test_native_current_signed_withdrawal_serializable_epoch_competition(native_signed_source,tmp_path,order):
    from threading import Event,Thread
    import time
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL
    material=_registered_publication_inputs(native_signed_source,tmp_path)
    raw,signature,digest=_integrated_signed_origin_withdrawal(material)
    release=Event();reader_ready=Event();writer_ready=Event();reader_done=Event();writer_done=Event();results={}
    def reader():
        try:
            with isolated_owner() as conn:
                conn.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
                conn.execute("SET LOCAL statement_timeout='10s'; SET LOCAL lock_timeout='8s'")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
                conn.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                results['reader_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                if order!='reader_first':reader_ready.set()
                try:
                    # Preserve 40001 from the real transaction; the malformed
                    # payload helper intentionally accepts only parser errors.
                    rows=[conn.execute(CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,_current_signed_params(ref)).fetchone() for ref in material['refs']]
                    assert all(rows)
                    assert [(bytes(r['raw_body']),bytes(r['signature'])) for r in rows]==material['documents']
                    results['reader_current']=True
                    if order=='reader_first':
                        reader_ready.set();assert release.wait(12)
                    conn.commit();results['reader_committed']=True
                except psycopg.errors.SerializationFailure as error:
                    results['reader_sqlstate']=error.sqlstate;conn.rollback()
        except BaseException as error:
            results['reader_error']=(type(error).__name__,str(error))
        finally:reader_done.set()
    def writer():
        try:
            with isolated_owner() as conn:
                conn.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
                conn.execute("SET LOCAL statement_timeout='10s'; SET LOCAL lock_timeout='8s'")
                conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",SCOPE.key)
                results['writer_pid']=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                conn.execute('SET SESSION AUTHORIZATION aos_provider_capacity_policy_publisher')
                if order=='reader_first':writer_ready.set()
                assert conn.execute('SELECT aos_capacity_publication_private.withdraw_origin(%s,%s) AS digest',(raw,signature)).fetchone()['digest']==digest
                if order!='reader_first':writer_ready.set();assert release.wait(12)
                if order=='withdrawal_rollback_first':conn.rollback();results['writer_rolled_back']=True
                else:conn.commit();results['writer_committed']=True
                conn.execute('RESET SESSION AUTHORIZATION');conn.commit()
        except BaseException as error:
            results['writer_error']=(type(error).__name__,str(error))
        finally:writer_done.set()
    rt,wt=Thread(target=reader),Thread(target=writer)
    first,ready,second,other_ready=(rt,reader_ready,wt,writer_ready) if order=='reader_first' else (wt,writer_ready,rt,reader_ready)
    first.start();blocked=False
    try:
        assert ready.wait(10),results
        second.start();assert other_ready.wait(10),results
        waiting,holding=('writer_pid','reader_pid') if order=='reader_first' else ('reader_pid','writer_pid')
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            with isolated_owner() as probe:
                blockers=probe.execute('SELECT pg_blocking_pids(%s) AS blockers',(results[waiting],)).fetchone()['blockers']
                probe.rollback()
            if results[holding] in blockers:blocked=True;break
            if reader_done.is_set() or writer_done.is_set():break
            time.sleep(.02)
        assert blocked,results
        assert not reader_done.is_set() and not writer_done.is_set(),results
    finally:
        release.set()
        if rt.ident:rt.join(12)
        if wt.ident:wt.join(12)
    assert not rt.is_alive() and not wt.is_alive(),results
    assert 'reader_error' not in results and 'writer_error' not in results,results
    if order=='withdrawal_first':
        assert results.get('reader_sqlstate')=='40001' and not results.get('reader_current'),results
    else:assert results.get('reader_current') and results.get('reader_committed'),results
    rolled_back=order=='withdrawal_rollback_first'
    assert results.get('writer_rolled_back' if rolled_back else 'writer_committed'),results
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for ref in material['refs']:
            row=_read_native_current_signed(owner,_current_signed_params(ref))
            assert (row is not None)==rolled_back
        assert owner.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchone()==dict(
            epoch=1 if rolled_back else 2,head_origin_hash=material['origin_hash'] if rolled_back else None)
        _assert_integrated_signed_history(owner,material,0 if rolled_back else 1)
        owner.rollback()
    print('NATIVE_CURRENT_SIGNED_EPOCH_COMPETITION '+order+' actual_blocker=true actual_commit_or_rollback=true history=exact')


@pytest.mark.parametrize('fault',[
    'valid','larger_supplier_limits','supplier','fingerprint','provider_hash',
    'extra_provider','evidence_hash','root_revision','allowed_mode','observation_age','future_observation',
    'rate_valid','rate_window_seconds','rate_window_anchor','rate_offset_equivalent',
    'supplier_basis_valid','supplier_basis_observation','low_concurrency','low_tokens',
    'policy_publisher','policy_key','attestation_window',
])
def test_native_signed_supplier_combination_keeps_original_approved_terms(native_signed_source,approved_command,tmp_path,fault):
    """Same stored original approvals and genuine signatures, never a caller flag."""
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import (
        check_native_capacity_supplier_inputs,authenticate_capacity_issuance_command)
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api import aip_provider_capacity_publication_store as native
    from datetime import timedelta
    from aos_api.aip_provider_capacity_source_issuer import ProviderCapacityIssuanceBlocked
    # Produce a new basis and Source approval through the original APIs. Never
    # mutate a stored approved payload or manufacture coherent approval hashes.
    if fault.startswith(('rate_','supplier_basis_')):
        from uuid import uuid4
        from datetime import timezone
        from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
        from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate
        from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
        from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source
        from aos_api.aip_action_models import DecideActionProposalRequest
        from aos_api.aip_action_store import canonical_hash
        f,old_command,basis,source,config=native_signed_source
        maker_principal,checker=approved_command[:2]
        raw=basis.model_dump(mode='python',by_alias=True)
        if fault.startswith('rate_'):
            raw['tokenLimit']=dict(mode='fixed_window_rate',unit='token',maxTokens=basis.token_limit.max_tokens,
                windowSeconds=60,windowAnchor=f['now'])
        else:raw['basisKind']='supplier_limit_claim'
        basis=ProviderCapacityBasisCandidate.model_validate(raw)
        saved=ProviderCapacityCandidateStore().create_basis(SCOPE,maker_principal,'signed-combination-basis-'+uuid4().hex,basis)
        source=source.model_copy(update={'basis_ref':FormalExactRef(assetType='ProviderCapacityBasisCandidateRevision',
            assetId=saved['candidate_id'],revision=1,contentHash=saved['content_hash'])})
        proposal=propose_provider_capacity_source(maker_principal,source,'signed-combination-proposal-'+uuid4().hex,source.valid_until)
        approved=decide_provider_capacity_source(checker,proposal.proposal.id,'signed-combination-approve-'+uuid4().hex,
            DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
                expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',
                reason='isolated original signed supplier combination',approvalExpiresAt=source.valid_until)))
        f['attestation']['tokenLimit']=basis.token_limit.model_dump(mode='python',by_alias=True)
        f['attestation']['observedAt']=basis.observed_at
        f['policy']['allowedTokenModes']=[basis.token_limit.mode]
        def actual_command():
            command,policy,attestation=old_command()
            return command.model_copy(update={
                'approved_proposal':FormalExactRef(assetType='ActionProposal',assetId=approved.proposal.id,
                    revision=2,contentHash=approved.proposal.proposal_hash),
                'approval_event':FormalExactRef(assetType='ActionApprovalEvent',assetId=approved.approvals[0].id,
                    revision=1,contentHash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True)))}),policy,attestation
        native_signed_source=(f,actual_command,basis,source,config)
    def change(f):
        att,pol=f['attestation'],f['policy']
        approved_source=native_signed_source[3]
        if fault=='larger_supplier_limits':
            att['maxConcurrency']+=1
            att['tokenLimit']['maxTokens']+=1
        elif fault=='supplier':att['supplierId']='different-signed-supplier'
        elif fault=='fingerprint':att['supplierAccountFingerprint']='d'*64
        elif fault=='provider_hash':att['providerRefs'][0]['contentHash']='d'*64
        elif fault=='extra_provider':
            att['providerRefs'].append(dict(att['providerRefs'][0],assetId='additional-signed-provider'))
        elif fault=='evidence_hash':att['evidenceRef']['contentHash']='d'*64
        elif fault=='root_revision':pol['attestationRootRevision']='sha256:'+'d'*64
        elif fault=='allowed_mode':
            pol['allowedTokenModes']=['fixed_window_rate' if att['tokenLimit']['mode']=='inflight_upper_bound' else 'inflight_upper_bound']
        elif fault=='observation_age':
            att['observedAt']=att['observedAt']-timedelta(days=2)
        elif fault=='future_observation':
            att['observedAt']=f['now']+timedelta(minutes=2)
        elif fault=='rate_window_seconds':att['tokenLimit']['windowSeconds']=120
        elif fault=='rate_window_anchor':att['tokenLimit']['windowAnchor']+=timedelta(seconds=1)
        elif fault=='rate_offset_equivalent':
            att['tokenLimit']['windowAnchor']=att['tokenLimit']['windowAnchor'].astimezone(timezone(timedelta(hours=5,minutes=30)))
        elif fault=='supplier_basis_observation':att['observedAt']+=timedelta(seconds=1)
        elif fault=='low_concurrency':
            assert att['maxConcurrency']>1
            att['maxConcurrency']-=1
        elif fault=='low_tokens':
            assert att['tokenLimit']['maxTokens']>1
            att['tokenLimit']['maxTokens']-=1
        elif fault=='policy_publisher':pol['attestationPublisher']='aos-capacity-source-policy'
        elif fault=='policy_key':pol['attestationKeyId']='different-signed-key'
        elif fault=='attestation_window':att['validUntil']=approved_source.valid_until-timedelta(seconds=1)
    material=_registered_publication_inputs(native_signed_source,tmp_path,signed_fault=change)
    command,policy,attestation=material['actual_command']()
    _,_,basis,source,_=native_signed_source
    maker=authenticate_capacity_issuance_command(command).subject
    accepted=fault in ('valid','larger_supplier_limits','rate_valid','rate_offset_equivalent','supplier_basis_valid')
    with connect_capacity_issuer(material['config'],SCOPE) as issuer:
        assert issuer.pgconn.used_password
        if accepted:
            original=check_native_capacity_supplier_inputs(issuer,command,policy,attestation,trust_roots=material['provider'])
            assert original.execution_allowed is False
        else:
            with pytest.raises(ProviderCapacityIssuanceBlocked):
                check_native_capacity_supplier_inputs(issuer,command,policy,attestation,trust_roots=material['provider'])
    params=ProviderCapacitySourceActionGuard._combination_params(SCOPE,source,maker)
    params.update(proposal_id=command.approved_proposal.asset_id,
        proposal_revision=command.approved_proposal.revision,proposal_hash=command.approved_proposal.content_hash,
        approval_event_id=command.approval_event.asset_id,approval_event_hash=command.approval_event.content_hash)
    for name,ref in zip(('policy','attestation'),material['refs'][:2]):
        params.update({name+'_id':ref['assetId'],name+'_revision':str(ref['revision']),name+'_hash':ref['contentHash']})
    statement=getattr(native,'CAPACITY_NATIVE_SIGNED_SUPPLIER_COMBINATION_SQL',None)
    assert statement is not None, 'Original signed supplier combination must be translated into native SQL'
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        for profile in (native.CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,native.CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):
            owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        # Both documents must independently pass S17: refusal must come from
        # the cross-contract comparison, not invalid signatures/registration.
        for ref in material['refs'][:2]:
            assert owner.execute(native.CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,_current_signed_params(ref)).fetchone() is not None
        row=owner.execute(statement,params).fetchone()
        assert (row is not None)==accepted
        if accepted:
            assert row['source']==source.model_dump(mode='json',by_alias=True)
            assert row['basis']==basis.model_dump(mode='json',by_alias=True)
            if fault=='valid':
                # Client selectors cannot substitute a different stored parent.
                for field in ('account_hash','basis_hash','policy_hash','attestation_hash','approval_event_hash','proposal_hash'):
                    wrong=dict(params);wrong[field]='d'*64
                    assert owner.execute(statement,wrong).fetchone() is None

        owner.rollback()
    print('S18_S19_SAME_ORIGINAL_SCRAM_AND_REGISTERED_SIGNATURES no_source_delivery')


@pytest.mark.parametrize('representation',['utc','accepted_offset','allocation_shorter','basis_shorter'])
def test_native_source_window_requires_original_request_allocation_and_basis(native_signed_source,approved_command,representation):
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api import aip_provider_capacity_publication_store as native
    _,actual_command,basis,source,config=native_signed_source
    from datetime import timedelta,timezone
    from uuid import uuid4
    from copy import deepcopy
    from psycopg.types.json import Jsonb
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    from aos_api.aip_provider_capacity_action import propose_provider_capacity_request,decide_provider_capacity_request
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourceCandidate
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    if representation!='utc':
        maker_principal,checker=approved_command[:2]
        if representation in ('accepted_offset','allocation_shorter'):
            with isolated_owner() as owner:
                raw_request=owner.execute('SELECT request_json FROM public.aip_provider_capacity_request WHERE request_id=%s',
                    (source.allocation_request_ref.asset_id,)).fetchone()['request_json']['application']
            application=ProviderCapacityRequest.model_validate(raw_request)
            if representation=='accepted_offset':
                offset=timezone(timedelta(hours=5,minutes=30))
                application=application.model_copy(update={'valid_from':application.valid_from.astimezone(offset),
                    'valid_until':application.valid_until.astimezone(offset)})
            saved=ProviderCapacityRequestStore().create(SCOPE,maker_principal,'window-request-'+uuid4().hex,application)
            proposal=propose_provider_capacity_request(maker_principal,saved['request_id'],'window-allocation-'+uuid4().hex,
                application.proposal_expires_at)
            deadline=source.valid_until-timedelta(seconds=30) if representation=='allocation_shorter' else source.valid_until
            approved=decide_provider_capacity_request(checker,proposal.proposal.id,'window-allocation-approve-'+uuid4().hex,
                DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
                    expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated original window',
                    approvalExpiresAt=deadline)))
            source=source.model_copy(update={
                'allocation_request_ref':FormalExactRef(assetType='ProviderCapacityRequest',assetId=saved['request_id'],
                    revision=1,contentHash=saved['request_hash']),
                'allocation_approval_ref':FormalExactRef(assetType='ActionApprovalEvent',assetId=approved.approvals[0].id,
                    revision=1,contentHash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True))),
                'valid_until':deadline})
        else:
            basis=basis.model_copy(update={'valid_until':source.valid_until-timedelta(seconds=30)})
            saved=ProviderCapacityCandidateStore().create_basis(SCOPE,maker_principal,'window-basis-'+uuid4().hex,basis)
            source=source.model_copy(update={'basis_ref':FormalExactRef(assetType='ProviderCapacityBasisCandidateRevision',
                assetId=saved['candidate_id'],revision=1,contentHash=saved['content_hash']),'valid_until':basis.valid_until})
        proposal=propose_provider_capacity_source(maker_principal,source,'window-source-'+uuid4().hex,source.valid_until)
        approved=decide_provider_capacity_source(checker,proposal.proposal.id,'window-source-approve-'+uuid4().hex,
            DecideActionProposalRequest.model_validate(dict(expectedProposalVersion=proposal.proposal.version,
                expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated original Source window',
                approvalExpiresAt=source.valid_until)))
        old_command=actual_command
        def actual_command():
            command,policy,attestation=old_command()
            return command.model_copy(update={'approved_proposal':FormalExactRef(assetType='ActionProposal',
                assetId=approved.proposal.id,revision=2,contentHash=approved.proposal.proposal_hash),
                'approval_event':FormalExactRef(assetType='ActionApprovalEvent',assetId=approved.approvals[0].id,
                revision=1,contentHash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True)))}),policy,attestation
    command,_,_=actual_command();maker=authenticate_capacity_issuance_command(command).subject
    with connect_capacity_issuer(config,SCOPE) as issuer:
        assert issuer.pgconn.used_password
        assert read_capacity_approved_claims(issuer,command).source==source
    params=ProviderCapacitySourceActionGuard._combination_params(SCOPE,source,maker)
    params.update(proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
        proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
        approval_event_hash=command.approval_event.content_hash)
    statement=getattr(native,'CAPACITY_NATIVE_SOURCE_WINDOW_SQL',None)
    assert statement is not None, 'Full original request/allocation/Source window combination is required'
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute("SET LOCAL TimeZone='UTC'")
        for profile in (native.CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,native.CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,
                        native.CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):owner.execute(profile)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        row=owner.execute(statement,params).fetchone()
        assert row is not None and row['source']==source.model_dump(mode='json',by_alias=True)
        assert row['basis']==basis.model_dump(mode='json',by_alias=True)
        # A caller's request selector cannot override the stored Source parent.
        assert owner.execute(statement,{**params,'request_id':'different-request','request_hash':'d'*64}).fetchone() is not None
        for fault in ('proposal_after_end','start_before_basis','end_after_minimum'):
            owner.execute('RESET ROLE');owner.execute('SAVEPOINT source_window_fault')
            modified=dict(params)
            try:
                original=owner.execute('SELECT * FROM public.aip_action_proposal WHERE proposal_id=%s',
                    (params['proposal_id'],)).fetchone()
                owner.execute("SET LOCAL session_replication_role='replica'")
                if fault=='proposal_after_end':
                    owner.execute('UPDATE public.aip_action_proposal SET expires_at=%s WHERE proposal_id=%s',
                        (source.valid_until+timedelta(seconds=1),params['proposal_id']))
                else:
                    changed=source.model_copy(update={
                        'valid_from':basis.valid_from-timedelta(microseconds=1)} if fault=='start_before_basis'
                        else {'valid_until':source.valid_until+timedelta(seconds=1)})
                    changed=ProviderCapacitySourceCandidate.model_validate(changed.model_dump(mode='python',by_alias=True))
                    payload=deepcopy(original['payload']);payload['sourceCandidate']=changed.model_dump(mode='json',by_alias=True)
                    binding=canonical_hash(dict(sourceCandidate=payload['sourceCandidate'],
                        actionTypeRevisionHash=original['action_type_snapshot']['revisionHash']))
                    snapshot=owner.execute('SELECT snapshot FROM public.aip_action_draft WHERE proposal_id=%s',
                        (params['proposal_id'],)).fetchone()['snapshot']
                    snapshot['payload']=payload;snapshot['actionBindingHash']=binding
                    proposal_hash=canonical_hash(snapshot)
                    owner.execute('UPDATE public.aip_action_draft SET snapshot=%s WHERE proposal_id=%s',
                        (Jsonb(snapshot),params['proposal_id']))
                    owner.execute('UPDATE public.aip_action_proposal SET payload=%s,action_binding_hash=%s,proposal_hash=%s WHERE proposal_id=%s',
                        (Jsonb(payload),binding,proposal_hash,params['proposal_id']))
                    owner.execute('UPDATE public.aip_action_approval_event SET action_binding_hash=%s,proposal_hash=%s WHERE approval_event_id=%s',
                        (binding,proposal_hash,params['approval_event_id']))
                    modified['proposal_hash']=proposal_hash
                    modified['approval_event_hash']=owner.execute(native.CAPACITY_APPROVAL_EVENT_PROJECTION_SQL,modified).fetchone()['hash']
                owner.execute("SET LOCAL session_replication_role='origin'")
                owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                assert owner.execute(native.CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL,modified).fetchone() is not None,fault
                assert owner.execute(statement,modified).fetchone() is None,fault
            finally:owner.execute('ROLLBACK TO SAVEPOINT source_window_fault')
            owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            assert owner.execute(statement,params).fetchone() is not None
        owner.rollback()
    print('ORIGINAL_SOURCE_WINDOW_ACTUAL_SCRAM native_window_only_no_source_delivery')


def test_original_request_large_offset_storage_boundary_is_not_source_authority(native_signed_source,approved_command):
    """Model acceptance is weaker than the actual original storage boundary."""
    from datetime import timedelta,timezone
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_authorization import ProviderCapacityRequest
    from aos_api.aip_provider_capacity_request_store import ProviderCapacityRequestStore
    from aos_api import aip_provider_capacity_publication_store as native
    _,_,_,source,_=native_signed_source
    with isolated_owner() as owner:
        raw=owner.execute('SELECT request_json FROM public.aip_provider_capacity_request WHERE request_id=%s',
            (source.allocation_request_ref.asset_id,)).fetchone()['request_json']['application']
    application=ProviderCapacityRequest.model_validate(raw)
    offset=timezone(timedelta(hours=23,minutes=59))
    application=application.model_copy(update={'valid_from':application.valid_from.astimezone(offset),
        'valid_until':application.valid_until.astimezone(offset)})
    application=ProviderCapacityRequest.model_validate(application.model_dump(mode='python',by_alias=True))
    key='original-offset-boundary-'+uuid4().hex
    # Actual original producer fails before a request/approval/Source exists.
    # This is a documented original boundary, not a native-window positive.
    with pytest.raises(psycopg.errors.InvalidTimeZoneDisplacementValue):
        ProviderCapacityRequestStore().create(SCOPE,approved_command[0],key,application)
    with isolated_owner() as owner:
        assert owner.execute('SELECT count(*) AS n FROM public.aip_provider_capacity_request WHERE idempotency_key=%s',(key,)).fetchone()['n']==0
        owner.execute(native.CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute(native.CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        parsed=owner.execute('SELECT aos_capacity_publication_private.read_original_capacity_application(%s) AS value',
            (Jsonb(application.model_dump(mode='json',by_alias=True)),)).fetchone()['value']
        assert parsed==application.model_dump(mode='json',by_alias=True)
        with pytest.raises(psycopg.errors.InvalidTimeZoneDisplacementValue):
            with owner.transaction():
                owner.execute('SELECT %s::timestamptz',(parsed['validFrom'],))
        decoded=owner.execute('SELECT instant FROM aos_capacity_publication_private.original_source_time(%s)',
            (Jsonb(parsed['validFrom']),)).fetchone()['instant']
        assert decoded==application.valid_from
        owner.rollback()
    print('ORIGINAL_REQUEST_MODEL_OFFSET_ACCEPTED_STORAGE22009_NO_REQUEST_NO_SOURCE native_decoder_only')


@pytest.mark.parametrize('fault',['valid','policy_hash','signer_publisher','signer_key','signer_revision','signer_public_key','short_window','root_expired','root_future','root_revoked'])
def test_native_signing_permit_binds_exact_policy_and_controlled_source_root(native_signed_source,tmp_path,fault):
    import base64
    from datetime import timedelta
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api import aip_provider_capacity_publication_store as native
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_formal_boundary import read_capacity_approved_claims
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    source=native_signed_source[3]
    def change(p):
        if fault=='policy_hash':p['sourcePolicyRef']['contentHash']='d'*64
        elif fault=='signer_publisher':p['signerPublisher']='different-source-signer'
        elif fault=='signer_key':p['signerKeyId']='different-source-key'
        elif fault=='signer_revision':p['signerRootRevision']='sha256:'+'d'*64
        elif fault=='signer_public_key':p['signerPublicKey']=base64.b64encode(bytes([7])*32).decode()
        elif fault=='short_window':p['validUntil']=source.valid_until-timedelta(seconds=1)
    def root_change(root):
        now=native_signed_source[0]['now']
        if fault=='root_expired':root['notAfter']=(now-timedelta(seconds=1)).isoformat()
        elif fault=='root_future':root['notBefore']=(now+timedelta(minutes=1)).isoformat()
        elif fault=='root_revoked':root['revokedAt']=(now-timedelta(seconds=1)).isoformat()
    material=_registered_publication_inputs(native_signed_source,tmp_path,permit_fault=change,source_root_fault=root_change)
    command,_,_=material['actual_command']();maker=authenticate_capacity_issuance_command(command).subject
    with connect_capacity_issuer(material['config'],SCOPE) as issuer:
        assert issuer.pgconn.used_password
        assert read_capacity_approved_claims(issuer,command).source==source
    params=ProviderCapacitySourceActionGuard._combination_params(SCOPE,source,maker)
    params.update(proposal_id=command.approved_proposal.asset_id,proposal_revision=command.approved_proposal.revision,
        proposal_hash=command.approved_proposal.content_hash,approval_event_id=command.approval_event.asset_id,
        approval_event_hash=command.approval_event.content_hash)
    for name,ref in (('policy',material['refs'][0]),('permit',material['refs'][2])):
        params.update({name+'_id':ref['assetId'],name+'_revision':str(ref['revision']),name+'_hash':ref['contentHash']})
    statement=getattr(native,'CAPACITY_NATIVE_SIGNING_PERMIT_COMBINATION_SQL',None)
    assert statement is not None,'S20 needs actual permit / separate controlled signer-root combination'
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        owner.execute(native.CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL)
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        for ref in (material['refs'][0],material['refs'][2]):
            assert owner.execute(native.CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,_current_signed_params(ref)).fetchone() is not None
        row=owner.execute(statement,params).fetchone()
        assert (row is not None)==(fault=='valid')
        if row:
            from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
            assert row['source']==source.model_dump(mode='json',by_alias=True)
            assert bytes(row['source_signer_public_key'])==material['source_key'].public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        owner.rollback()
    print('S20_REAL_PERMIT_AND_SEPARATE_SOURCE_SIGNER',fault,'no_source_delivery')
