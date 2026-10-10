"""Fixed catalog profile is explicit and bound to a complete trusted family."""
import hashlib
import re

import pytest


def test_complete_catalog_profile_binds_every_digest_and_keeps_legacy():
    from aos_api import aip_provider_capacity_catalog_audit_profile as profile
    from aos_api import aip_provider_capacity_occupation_epoch_profile as epoch
    from aos_api import aip_provider_capacity_publication_transaction as transaction
    from aos_api import aip_provider_capacity_occupation_source as occupation
    original = epoch._body(profile.store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL, profile.FACT)
    body = profile.catalog_fact_body()
    assert body != original
    assert body.count(profile.COLUMN_AFTER) == 2
    assert body.replace(profile.COLUMN_AFTER, profile.COLUMN_BEFORE) == original
    private = profile.catalog_private_statements()
    audit = profile._profile_body(private[-1])
    assert hashlib.sha256(body.encode()).hexdigest() in audit
    assert hashlib.sha256(original.encode()).hexdigest() not in audit
    audit_hash = hashlib.sha256(audit.encode()).hexdigest()
    for ddl in profile.catalog_public_statements(include_consumer=True)[5:]:
        if ddl.startswith('CREATE OR REPLACE FUNCTION public.'):
            assert ddl.count(audit_hash) == 1
    occ = profile.catalog_occupation_statements()
    assert occ[0] == occupation.occupation_source_statements()[0]
    assert occ[4].count(audit_hash) == 1
    assert profile.catalog_public_manifest(include_consumer=True)
    # Legacy public/private identities still embed their original FACT digest.
    legacy_audit = epoch._body(transaction.source_private_installation_audit_sql(),
                              epoch.INSTALLATION, 'audit')
    assert hashlib.sha256(original.encode()).hexdigest() in legacy_audit
    assert hashlib.sha256(body.encode()).hexdigest() not in legacy_audit



def test_catalog_compiler_fails_closed_on_original_predicate_drift(monkeypatch):
    from aos_api import aip_provider_capacity_catalog_audit_profile as profile
    monkeypatch.setattr(profile.store,'CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL',profile.store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL.replace(profile.COLUMN_BEFORE,'true',1))
    with pytest.raises(ValueError):
        profile.catalog_fact_body()


def test_native_complete_catalog_identity_partial_hybrid_acl_and_restoration():
    """Real catalog identities only; signed Source business positive is separate."""
    import os
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.conninfo import conninfo_to_dict
    from aos_api import aip_provider_capacity_catalog_audit_profile as profile
    from aos_api import aip_provider_capacity_occupation_epoch_profile as epoch
    from aos_api import aip_provider_capacity_publication_transaction as transaction
    from aos_api import aip_provider_capacity_occupation_source as occupation

    if not os.getenv('AOS_CATALOG_PROFILE_TEST_CLUSTER'):
        pytest.skip('explicit owned native catalog lab required')
    params = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    assert params['dbname'].startswith('aos_test_') and params['dbname'].endswith('_ti4_test')
    assert params['host'] == '127.0.0.1' and params['port'] == '5441'
    params.update(passfile=os.environ['AOS_TEST_PGPASSFILE'], row_factory=dict_row)
    snapshot_sql = """SELECT p.oid,p.prosrc,p.proowner::text,p.proacl::text,p.proconfig,p.prosecdef,
        p.proisstrict,p.provolatile,p.proparallel FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname IN ('public','aos_capacity_publication_private') ORDER BY p.oid"""
    with psycopg.connect(**params) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        assert conn.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'] == os.environ['AOS_CATALOG_PROFILE_TEST_CLUSTER']
        before = conn.execute(snapshot_sql).fetchall()
        assert profile.catalog_profile_is_installed(conn) is False
        with conn.transaction(force_rollback=True):
            conn.execute("SET LOCAL ROLE aos_runtime")
            assert profile.catalog_profile_is_installed(conn) is False
        with conn.transaction(force_rollback=True):
            # This retained clone has original FACT/PAIR but no Source installer.
            # Create the trusted baseline audit as an owned test prerequisite,
            # retaining all checks; never claim its runtime audit passed.
            conn.execute(transaction.source_private_installation_audit_sql())
            conn.execute('ALTER FUNCTION '+epoch.INSTALLATION+' OWNER TO aos_capacity_publication_owner')
            conn.execute('REVOKE ALL ON FUNCTION '+epoch.INSTALLATION+' FROM PUBLIC')
            with conn.transaction(force_rollback=True):
                conn.execute(profile.catalog_private_statements()[0])
                with pytest.raises(ValueError,match=profile.ERROR):
                    profile.catalog_profile_is_installed(conn)
            for statement in profile.catalog_installation_statements(include_consumer=True):
                conn.execute(statement)
            assert profile.catalog_profile_is_installed(conn) is True
            assert epoch.occupation_epoch_profile_is_installed(conn) is True
            with conn.transaction(force_rollback=True):
                conn.execute("SET LOCAL ROLE aos_runtime")
                assert profile.catalog_profile_is_installed(conn) is True
            transaction.require_source_public_entry_definitions(conn)
            occupation._require_definitions(conn)
            # Preserve full native original FACT runtime checks in the new body.
            conn.execute('SELECT '+profile.FACT)
            mutations = [
                epoch._definition(profile.FACT,epoch._body(profile.store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL,profile.FACT)),
                epoch._definition(epoch.INSTALLATION,profile._profile_body(epoch.occupation_epoch_profile_statements()[-1])),
                'REVOKE EXECUTE ON FUNCTION '+epoch.NEUTRAL_LOCK+' FROM aos_capacity_publication_owner',
                'GRANT EXECUTE ON FUNCTION '+profile.FACT+' TO PUBLIC',
                'ALTER FUNCTION '+profile.FACT+' SECURITY DEFINER',
                'ALTER FUNCTION '+profile.FACT+' SET search_path=public',
                'ALTER FUNCTION '+profile.FACT+' OWNER TO aos_app',
                'ALTER FUNCTION '+profile.FACT+' STRICT',
                'ALTER FUNCTION '+profile.FACT+' STABLE',
            ]
            for mutation in mutations:
                with conn.transaction(force_rollback=True):
                    conn.execute(mutation)
                    with pytest.raises(ValueError,match=profile.ERROR):
                        profile.catalog_profile_is_installed(conn)
                assert profile.catalog_profile_is_installed(conn) is True
            # Public and occupation consumers reject an old body under new identity.
            old_public = epoch.occupation_public_source_profile_statements(include_consumer=True)[4]
            with conn.transaction(force_rollback=True):
                conn.execute(old_public)
                with pytest.raises(transaction.CapacityPublicationBoundaryBlocked):
                    transaction.require_source_public_entry_definitions(conn)
            old_occ = occupation.occupation_source_statements()[4].replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
            with conn.transaction(force_rollback=True):
                conn.execute(old_occ)
                with pytest.raises(ValueError):
                    occupation._require_definitions(conn)
        assert conn.execute(snapshot_sql).fetchall() == before
        conn.rollback()
    with psycopg.connect(**params) as restored:
        restored.execute('SET TRANSACTION READ ONLY')
        assert restored.execute(snapshot_sql).fetchall() == before
        assert profile.catalog_profile_is_installed(restored) is False
        restored.rollback()


pytest_plugins = ('tests.aip.test_capacity_source_publication_transaction_pg',)


@pytest.mark.parametrize('native_original_fact_reader', ['distinct'], indirect=True)
def test_catalog_profile_real_signed_source_commit_and_fresh_consumer(exact_public_source_caller):
    """Original roots/approvals/Source, actual COMMIT, new native transaction."""
    import json
    import os
    import time
    from pathlib import Path
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from tests.aip.test_capacity_source_publication_transaction_pg import _refresh_native_facts_transaction
    from aos_api import aip_provider_capacity_catalog_audit_profile as profile
    from aos_api import aip_provider_capacity_occupation_epoch_profile as epoch
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_source_consumer import read_current_capacity_source

    caller, packet, material, _ = exact_public_source_caller
    caller.rollback()
    with isolated_owner() as admin:
        before = admin.execute('SELECT prosrc FROM pg_proc WHERE oid=to_regprocedure(%s)',(profile.FACT,)).fetchone()['prosrc']
        assert admin.execute("SELECT to_regprocedure('public.read_current_capacity_source(bytea,jsonb)')").fetchone()['to_regprocedure'] is None
        for statement in profile.catalog_public_statements(include_consumer=True):
            admin.execute(statement)
        assert profile.catalog_profile_is_installed(admin)
        with admin.transaction():
            admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            admin.execute('SELECT '+epoch.INSTALLATION)
    record = {'database': caller.info.dbname, 'private_runtime_audit_passed': True,
              'original_source_ttl_unchanged': True, 'execution_allowed': False}
    try:
        _refresh_native_facts_transaction(caller)
        command, _, _ = material['actual_command']()
        started = time.monotonic()
        asset = 'catalog-source-' + uuid4().hex
        pending = caller.execute('SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
            (packet,command.idempotency_key,asset,Jsonb(material['refs'][-1]))).fetchone()
        raw = bytes(pending['source_raw'])
        signed = material['source_key'].sign(raw)
        published = caller.execute('SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
            (command.idempotency_key,raw,signed)).fetchone()
        caller.commit()
        record.update(actual_caller_commit=True, publication_seconds=round(time.monotonic()-started,6),
                      asset_id=asset, content_hash=published['content_hash'])
        source = parse_signed_capacity_body(raw,PublishedProviderCapacitySourceV2)
        exact = FormalExactRef(asset_type='ProviderCapacitySourceRevision',asset_id=asset,
                              revision=published['revision'],content_hash=published['content_hash'])
        _refresh_native_facts_transaction(caller)
        identity = caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        assert identity['xid'] != source.issuance_context.transaction_id
        current, _, _ = material['actual_command']()
        consumed = read_current_capacity_source(caller,current,exact)
        assert consumed.model_dump(mode='json',by_alias=True) == source.model_dump(mode='json',by_alias=True)
        assert consumed.execution_allowed is False
        record.update(fresh_native_xid=True,current_source_exact=True,
                      publication_and_first_consume_seconds=round(time.monotonic()-started,6))
        caller.rollback()
    finally:
        caller.rollback()
        with isolated_owner() as admin:
            admin.execute('DROP FUNCTION public.read_current_capacity_source(bytea,jsonb)')
            for statement in epoch.legacy_public_source_restoration_statements():
                admin.execute(statement)
            admin.execute(epoch._definition(profile.FACT,before))
            assert admin.execute('SELECT prosrc FROM pg_proc WHERE oid=to_regprocedure(%s)',(profile.FACT,)).fetchone()['prosrc'] == before
            assert profile.catalog_profile_is_installed(admin) is False
        record['original_function_identity_restored'] = True
        if os.getenv('AOS_CATALOG_SIGNED_EVIDENCE'):
            path = Path(os.environ['AOS_CATALOG_SIGNED_EVIDENCE'])/'source-result.json'
            with path.open('x') as out:
                json.dump(record,out,indent=2);out.write('\n')
