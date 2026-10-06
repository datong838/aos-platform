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
