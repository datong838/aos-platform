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
