"""Complete publication boundary work; this initial RED is not full-chain proof."""
import psycopg
import pytest

from tests.aip.test_provider_capacity_source_pg import (
    native_signed_source, approved_command, private_database, signed_capacity_documents,
    source_proposal, source_inputs, drafted,
)
from tests.aip.test_provider_capacity_request_pg import original_inputs, SCOPE


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
        require_original_fact_boundary(owner)
        with pytest.raises(CapacityPublicationBoundaryBlocked):
            with owner.transaction():
                if fault=='database_create':
                    from psycopg import sql
                    owner.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO aos_capacity_publication_owner').format(sql.Identifier(owner.info.dbname)))
                else:
                    owner.execute(statements[fault])
                require_original_fact_boundary(owner)
        require_original_fact_boundary(owner)


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


def _registered_publication_inputs(native_signed_source,tmp_path):
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
    source_key=Ed25519PrivateKey.generate()
    source_public=source_key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    source_root=dict(f['roots'][0],publisher='isolated-source-signer',keyId='isolated-source-key',
        publicKey=base64.b64encode(source_public).decode())
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
        origin_hash=origin_hash,snapshot_hash=transport.content_hash,source_key=source_key)


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
