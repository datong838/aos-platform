"""Complete b90 evaluator acceptance, starting with isolated identity admission.

Session-authorization fault tests prove role checks only, never SCRAM or business
authority. A separate temporary LOGIN test proves actual SCRAM and is cleaned
after verifying its members and shared dependencies. No business ACL is granted.
"""
import os
from contextlib import contextmanager, nullcontext

import psycopg
from psycopg import sql
import pytest

from aos_api.aip_binding_evaluator_connection import (
    BindingEvaluatorConnectionBlocked, BindingEvaluatorDatabaseConfig,
    BindingEvaluatorConnectionFactory, EVALUATOR_LOGIN, _require_identity,
)
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


def _migration():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_144_binding_evaluator_boundary.py'
    spec = importlib.util.spec_from_file_location('binding_evaluator_a144_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(tmp_path, database):
    tmp_path.chmod(0o700)
    passfile = tmp_path / 'passfile'
    passfile.write_text('', encoding='utf-8')
    passfile.chmod(0o600)
    return BindingEvaluatorDatabaseConfig('127.0.0.1', 5432, database, passfile)


def test_formal_evaluator_migration_reserves_safe_identity_and_bounded_acl():
    with isolated_owner() as conn:
        row = conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,'
            'rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
        assert row is not None, 'formal evaluator boundary is missing'
        assert all(value is False for value in row.values())
        assert conn.execute('SELECT count(*) AS n FROM pg_auth_members WHERE '
            'roleid=%s::regrole OR member=%s::regrole', (EVALUATOR_LOGIN, EVALUATOR_LOGIN)).fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM pg_class WHERE relowner=%s::regrole',
            (EVALUATOR_LOGIN,)).fetchone()['n'] == 0
        for table in ('aip_action_approval_event', 'aip_provider_health_observation',
                      'aip_budget_reservation', 'aip_model_capacity_reservation',
                      'aip_license_source_issuance', 'aip_skill_binding'):
            for permission in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                assert not conn.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',
                    (EVALUATOR_LOGIN, 'public.' + table, permission)).fetchone()['allowed']
        for column in ('status', 'health', 'secret_ref', 'capability_ref'):
            assert not conn.execute("SELECT has_column_privilege(%s,'public.aip_capability_binding',%s,'UPDATE') AS allowed",
                (EVALUATOR_LOGIN, column)).fetchone()['allowed']
        for table in ('aip_agent_registry_receipt', 'aip_binding_evaluation_proof'):
            assert conn.execute("SELECT has_table_privilege(%s,%s,'INSERT') AS allowed",
                (EVALUATOR_LOGIN, 'public.' + table)).fetchone()['allowed']


def test_formal_evaluator_has_three_real_deferred_commit_guards():
    with isolated_owner() as conn:
        rows = conn.execute("SELECT c.relname,t.tgdeferrable,t.tginitdeferred FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid WHERE t.tgname LIKE 'binding_evaluator_atomic_%_a0v144'").fetchall()
        assert {r['relname'] for r in rows} == {
            'aip_capability_binding', 'aip_agent_registry_receipt', 'aip_binding_evaluation_proof'}
        assert all(r['tgdeferrable'] and r['tginitdeferred'] for r in rows)


def test_formal_evaluator_exact_column_acl_and_function_boundaries():
    migration = _migration()
    with isolated_owner() as conn:
        expected = set(migration.LOCK_COLUMNS) | {
            ('aip_capability_binding', col) for col in migration.BINDING_UPDATE_COLUMNS}
        columns = conn.execute("SELECT table_name,column_name FROM information_schema.columns "
            "WHERE table_schema='public'").fetchall()
        actual = {(c['table_name'], c['column_name']) for c in columns
            if conn.execute("SELECT has_column_privilege(%s,%s,%s,'UPDATE') AS allowed",
                (EVALUATOR_LOGIN, 'public.' + c['table_name'], c['column_name'])).fetchone()['allowed']}
        assert actual == expected
        for name in ('aip_provider_health_epoch', 'aip_skill_binding', 'aip_agent_instance'):
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'SELECT') AS allowed",
                (EVALUATOR_LOGIN, 'public.' + name)).fetchone()['allowed']
        assert conn.execute("SELECT has_function_privilege(%s,"
            "'public.aos_provider_health_epoch_lock(text,text,jsonb,boolean)','EXECUTE') AS allowed",
            (EVALUATOR_LOGIN,)).fetchone()['allowed']
        assert not conn.execute("SELECT has_function_privilege(%s,"
            "'public.binding_evaluator_atomic_triple_a0v144()','EXECUTE') AS allowed",
            (EVALUATOR_LOGIN,)).fetchone()['allowed']


def test_formal_evaluator_scoped_rls_is_enabled_forced_and_restrictive():
    migration = _migration()
    scoped = set(migration.SCOPED_READ) | {'aip_action_proposal', 'aip_action_draft', 'aip_action_approval_event'}
    with isolated_owner() as conn:
        rows = conn.execute('SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,p.polpermissive '
            'FROM pg_class c LEFT JOIN pg_policy p ON p.polrelid=c.oid '
            "AND p.polname='binding_evaluator_restrict_a0v144' WHERE c.relname=ANY(%s)",
            (list(scoped),)).fetchall()
        assert {r['relname'] for r in rows} == scoped
        assert all(r['relrowsecurity'] and r['relforcerowsecurity'] and r['polpermissive'] is False for r in rows)


def test_formal_evaluator_shared_lock_cannot_modify_original_owner_or_canary():
    import uuid
    subject = 'a144-lock-only-' + uuid.uuid4().hex
    with isolated_owner() as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO meta_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",
            (*SCOPE.key, subject))
        owner.commit()
        owner.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(EVALUATOR_LOGIN)))
        try:
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
            assert owner.execute('SELECT subject FROM meta_membership WHERE subject=%s FOR SHARE',
                (subject,)).fetchone()['subject'] == subject
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match='BINDING_EVALUATOR_READ_LOCK_ONLY'):
                with owner.transaction():
                    owner.execute('UPDATE meta_membership SET subject=subject WHERE subject=%s', (subject,))
            owner.execute("SELECT set_config('aos.org_id','dev-org',true)")
            assert owner.execute('SELECT subject FROM meta_membership WHERE subject=%s', (subject,)).fetchone() is None
        finally:
            owner.rollback()
            owner.execute('RESET SESSION AUTHORIZATION')
            owner.execute('DELETE FROM meta_membership WHERE subject=%s', (subject,))
            owner.commit()


def test_formal_evaluator_canary_cannot_initialize_health_epoch_through_definer():
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    provider = 'a144-canary-' + uuid4().hex
    with isolated_owner() as owner:
        owner.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(EVALUATOR_LOGIN)))
        try:
            owner.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                owner.execute('SELECT public.aos_provider_health_epoch_lock(%s,%s,%s,true)',
                    ('dev-org','dev-project',Jsonb(dict(assetType='ProviderInstanceRevision',assetId=provider))))
        finally:
            owner.rollback()
            owner.execute('RESET SESSION AUTHORIZATION')
        assert owner.execute('SELECT count(*) AS n FROM public.aip_provider_health_epoch WHERE provider_id=%s',
            (provider,)).fetchone()['n'] == 0


@contextmanager
def _temporary_fixed_evaluator_login(owner):
    """Isolated SCRAM fault fixture. Restore migration identity, never drop shared ACL."""
    import secrets
    from pathlib import Path
    from tempfile import TemporaryDirectory
    assert owner.info.dbname.startswith('aos_test_') and owner.info.port == 5433
    attributes = owner.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,'
        'rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
    assert attributes is not None and all(value is False for value in attributes.values())
    secret = secrets.token_urlsafe(32)
    owner.execute("SET LOCAL password_encryption='scram-sha-256'")
    owner.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(EVALUATOR_LOGIN), sql.Literal(secret)))
    owner.commit()
    try:
        with TemporaryDirectory(prefix='a144-private-') as directory:
            path = Path(directory) / 'pgpass'
            path.write_text(f'127.0.0.1:5433:{owner.info.dbname}:{EVALUATOR_LOGIN}:{secret}\n')
            path.chmod(0o600)
            config = BindingEvaluatorDatabaseConfig('127.0.0.1', 5433, owner.info.dbname, path)
            yield BindingEvaluatorConnectionFactory(config)
    finally:
        owner.rollback()
        owner.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(EVALUATOR_LOGIN)))
        owner.commit()


def assert_binding_evaluator_atomic_boundary(installation_id):
    """Signed-installation mechanism faults only; no synthetic READY is committed.

    Content objects below deliberately lack business provenance. They exercise
    the atomic database boundary, never the still-pending eight-fact command.
    """
    from datetime import timedelta
    import json
    from pathlib import Path
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from aos_api.aip_budget_store import canonical_hash
    observed = []
    with isolated_owner() as owner:
        install = owner.execute('SELECT installation_id,current_revision,active_revision,etag_version '
            'FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s',
            (*SCOPE.key, installation_id)).fetchone()
        assert install['active_revision'] == install['current_revision']
        with _temporary_fixed_evaluator_login(owner) as factory:
            for fault in ('control_rollback', 'binding_only', 'receipt_only', 'proof_only', 'hash', 'result_version', 'expiry', 'historical_receipt'):
                binding = 'a144-mechanism-' + uuid4().hex
                receipt = 'a144-receipt-' + uuid4().hex
                proof = 'a144-proof-' + uuid4().hex
                owner.execute("""INSERT INTO aip_capability_binding(org_id,project_id,binding_id,
                    capability_ref,secret_ref,health,network_policy_revision,quota_policy_revision,
                    timeout_ms,max_concurrency,status,version) VALUES(%s,%s,%s,%s,'secret://test-only',
                    'unknown','test-only','test-only',1000,1,'provisioning',1)""",
                    (*SCOPE.key, binding, Jsonb(dict(assetType='CapabilityRevision',assetId='atomic-mechanism',
                        revision=1,contentHash='a'*64))))
                owner.commit()
                historical_checked_at = None
                if fault == 'historical_receipt':
                    historical_checked_at = owner.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    owner.execute("""INSERT INTO aip_agent_registry_receipt(org_id,project_id,receipt_id,operation,
                        idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at)
                        VALUES(%s,%s,%s,'capability_binding.evaluate',%s,%s,%s,%s,'applied','test-only',%s)""",
                        (*SCOPE.key,receipt,receipt,'a'*64,
                         Jsonb(dict(resourceType='CapabilityBinding',resourceId=binding,authority='postgresql')),
                         Jsonb(dict(resourceType='CapabilityBindingReadiness',resourceId=binding,revision='2',authority='postgresql')),
                         historical_checked_at))
                    owner.commit()
                # Only proof-only needs an old unrelated Receipt to satisfy its FK.
                if fault == 'proof_only':
                    owner.execute("""INSERT INTO aip_agent_registry_receipt(org_id,project_id,receipt_id,operation,
                        idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at)
                        VALUES(%s,%s,%s,'a144.maintenance-fixture',%s,%s,'{}','{}','applied','test-only',clock_timestamp())""",
                        (*SCOPE.key,receipt,receipt,'a'*64))
                    owner.commit()
                phase = 'opening'
                expected = (nullcontext() if fault == 'control_rollback' else
                    pytest.raises(psycopg.errors.CheckViolation, match='BINDING_EVALUATOR_ATOMIC_TRIPLE_REQUIRED'))
                with expected as failure:
                    with factory(SCOPE) as conn:
                        assert conn.pgconn.used_password
                        pid = conn.info.backend_pid
                        checked_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                        if historical_checked_at is not None:
                            checked_at = historical_checked_at
                        valid_until = checked_at + timedelta(seconds=20)
                        if fault == 'expiry':
                            valid_until = checked_at + timedelta(milliseconds=100)
                        if fault not in ('receipt_only', 'proof_only'):
                            conn.execute("UPDATE aip_capability_binding SET version=2,dependency_snapshot_hash=%s,"
                                "operational_readiness='available',last_evaluated_at=%s,readiness_expires_at=%s "
                                'WHERE org_id=%s AND project_id=%s AND binding_id=%s',
                                ('b'*64,checked_at,valid_until,*SCOPE.key,binding))
                        if fault not in ('binding_only', 'proof_only', 'historical_receipt'):
                            resource = dict(resourceType='CapabilityBinding',resourceId=binding,authority='postgresql')
                            result = dict(resourceType='CapabilityBindingReadiness',resourceId=binding,
                                revision='3' if fault == 'result_version' else '2',authority='postgresql')
                            conn.execute("""INSERT INTO aip_agent_registry_receipt(org_id,project_id,receipt_id,operation,
                                idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at)
                                VALUES(%s,%s,%s,'capability_binding.evaluate',%s,%s,%s,%s,'applied','test-only',%s)""",
                                (*SCOPE.key,receipt,receipt,'a'*64,Jsonb(resource),Jsonb(result),checked_at))
                        if fault not in ('binding_only', 'receipt_only'):
                            facts = {name: {'testOnly': 'atomic-mechanism'} for name in
                                ('Provider','Model','Policy','Route','Eval','Health','Capacity','Price','Budget')}
                            facts.update(Source=[{'testOnly': True}],Owners=[{'testOnly': True}],Installation={
                                'installationId':str(installation_id),'revision':install['current_revision'],
                                'etag':install['etag_version']})
                            conn.execute("""INSERT INTO aip_binding_evaluation_proof(org_id,project_id,proof_id,
                                binding_id,binding_version,installation_id,installation_etag,receipt_id,
                                legacy_dependency_hash,facts_hash,facts,checked_at,valid_until)
                                VALUES(%s,%s,%s,%s,2,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (*SCOPE.key,proof,binding,installation_id,install['etag_version'],receipt,
                                 'b'*64,'c'*64 if fault == 'hash' else canonical_hash(facts),Jsonb(facts),checked_at,valid_until))
                        if fault == 'expiry':
                            # Read back all three before the real context-manager COMMIT.
                            assert conn.execute('SELECT count(*) AS n FROM aip_binding_evaluation_proof WHERE proof_id=%s',
                                (proof,)).fetchone()['n'] == 1
                            conn.execute('SELECT pg_sleep(0.15)')
                        if fault == 'control_rollback':
                            conn.execute('SET CONSTRAINTS binding_evaluator_atomic_binding_a0v144, '
                                'binding_evaluator_atomic_receipt_a0v144, binding_evaluator_atomic_proof_a0v144 IMMEDIATE')
                            conn.rollback()  # Synthetic facts must never certify business readiness.
                            phase = 'rollback'
                        else:
                            phase = 'commit'
                assert phase == ('rollback' if fault == 'control_rollback' else 'commit'), 'unexpected statement-stage failure'
                owner.rollback()
                assert owner.execute('SELECT version,operational_readiness FROM aip_capability_binding WHERE binding_id=%s',
                    (binding,)).fetchone() == {'version': 1, 'operational_readiness': 'unknown'}
                assert owner.execute('SELECT count(*) AS n FROM aip_agent_registry_receipt WHERE receipt_id=%s',
                    (receipt,)).fetchone()['n'] == (1 if fault in ('proof_only', 'historical_receipt') else 0)
                assert owner.execute('SELECT count(*) AS n FROM aip_binding_evaluation_proof WHERE proof_id=%s',
                    (proof,)).fetchone()['n'] == 0
                observed.append(dict(fault=fault, pid=pid, phase=phase,
                    sqlstate=failure.value.sqlstate if failure is not None else None,
                    error=failure.value.diag.message_primary if failure is not None else None, bindingVersionAfter=1,
                    newReceiptAfter=0, proofAfter=0, usedScram=True))
        attributes = owner.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,'
            'rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
        assert all(value is False for value in attributes.values())
        evidence = Path(__file__).resolve().parents[4] / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob90/implementation/a144-commit-facts.json'
        evidence.write_text(json.dumps(dict(database=owner.info.dbname, host=owner.info.host,
            port=owner.info.port, cases=observed, restoredRoleAttributes=attributes,
            authorization='MECHANISM_FAULTS_ONLY_NO_BUSINESS_READY'), indent=2) + '\n')


@pytest.mark.parametrize('fault', ['outgoing_membership', 'incoming_membership', 'search_path'])
def test_evaluator_rejects_identity_drift_in_actual_pg(tmp_path, fault):
    with isolated_owner() as conn:
        conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
        config = _config(tmp_path, conn.info.dbname)
        with conn.transaction(force_rollback=True):
            existing = conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
            if existing is None:
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(EVALUATOR_LOGIN)))
            else:
                conn.execute(sql.SQL('ALTER ROLE {} LOGIN').format(sql.Identifier(EVALUATOR_LOGIN)))
            if fault == 'outgoing_membership':
                conn.execute(sql.SQL('GRANT {} TO aos_runtime').format(sql.Identifier(EVALUATOR_LOGIN)))
            elif fault == 'incoming_membership':
                conn.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(EVALUATOR_LOGIN)))
            conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(EVALUATOR_LOGIN)))
            try:
                conn.execute("SET LOCAL statement_timeout='10s'")
                conn.execute("SET LOCAL lock_timeout='5s'")
                conn.execute("SET LOCAL idle_in_transaction_session_timeout='10s'")
                conn.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                if fault == 'search_path':
                    conn.execute('SET LOCAL search_path=public,pg_catalog')
                with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_DATABASE_IDENTITY_REQUIRED'):
                    _require_identity(conn, config, SCOPE)
            finally:
                conn.execute('RESET SESSION AUTHORIZATION')


def test_evaluator_private_passfile_rejects_hardlink(tmp_path):
    config = _config(tmp_path, 'aos_test_identity')
    alias = tmp_path / 'alias'
    os.link(config.passfile, alias)
    with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_EXACT_PRIVATE_CONFIGURATION_REQUIRED'):
        BindingEvaluatorDatabaseConfig(config.host, config.port, config.database, config.passfile)


def test_evaluator_actual_scram_admission_and_live_outgoing_membership_rejection(tmp_path):
    import secrets
    with isolated_owner() as owner:
        original = owner.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,'
            'rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
        if original is not None:
            assert all(value is False for value in original.values())
        secret = secrets.token_urlsafe(32)
        owner.execute("SET LOCAL password_encryption='scram-sha-256'")
        if original is None:
            owner.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                    sql.Identifier(EVALUATOR_LOGIN), sql.Literal(secret)))
        else:
            owner.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(
                sql.Identifier(EVALUATOR_LOGIN), sql.Literal(secret)))
        database = owner.info.dbname
        owner.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(
            sql.Identifier(database), sql.Identifier(EVALUATOR_LOGIN)))
        owner.commit()
        try:
            config = _config(tmp_path, database)
            config.passfile.write_text(
                f'127.0.0.1:{owner.info.port}:{database}:{EVALUATOR_LOGIN}:{secret}\n', encoding='utf-8')
            config = BindingEvaluatorDatabaseConfig('127.0.0.1', owner.info.port, database, config.passfile)
            factory = BindingEvaluatorConnectionFactory(config)
            with factory(SCOPE) as actual:
                assert actual.pgconn.used_password
                assert actual.execute('SELECT session_user AS login,current_user AS role').fetchone() == {
                    'login': EVALUATOR_LOGIN, 'role': EVALUATOR_LOGIN}
                assert actual.isolation_level == psycopg.IsolationLevel.SERIALIZABLE
                assert actual.execute('SHOW search_path').fetchone()['search_path'].replace(' ', '') == 'pg_catalog,public,pg_temp'
                actual.execute('CREATE TEMP TABLE aip_model_route_head(fake_head boolean)')
                assert actual.execute("SELECT to_regclass('aip_model_route_head')="
                    "'public.aip_model_route_head'::regclass AS original").fetchone()['original']
            original_passfile = config.passfile.read_text(encoding='utf-8')
            config.passfile.write_text(original_passfile.replace(secret, secrets.token_urlsafe(32)), encoding='utf-8')
            with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_CONNECTION_FAILED'):
                with factory(SCOPE):
                    pytest.fail('wrong password admitted')
            config.passfile.write_text(original_passfile, encoding='utf-8')
            owner.execute(sql.SQL('GRANT {} TO aos_runtime').format(sql.Identifier(EVALUATOR_LOGIN)))
            owner.commit()
            with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_DATABASE_IDENTITY_REQUIRED'):
                with factory(SCOPE):
                    pytest.fail('membership drift admitted')
        finally:
            owner.execute(sql.SQL('REVOKE {} FROM aos_runtime').format(sql.Identifier(EVALUATOR_LOGIN)))
            owner.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM {}').format(
                sql.Identifier(database), sql.Identifier(EVALUATOR_LOGIN)))
            owner.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(EVALUATOR_LOGIN)))
            assert owner.execute('SELECT count(*) AS n FROM pg_auth_members WHERE '
                'roleid=%s::regrole OR member=%s::regrole', (EVALUATOR_LOGIN, EVALUATOR_LOGIN)).fetchone()['n'] == 0
            if original is None:
                assert owner.execute("SELECT count(*) AS n FROM pg_shdepend WHERE refclassid='pg_authid'::regclass "
                    'AND refobjid=%s::regrole', (EVALUATOR_LOGIN,)).fetchone()['n'] == 0
                owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(EVALUATOR_LOGIN)))
            owner.commit()
            restored = owner.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,'
                'rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
            assert restored == original


@pytest.mark.parametrize('fault', ['none', 'missing', 'revision', 'hash', 'ambiguous', 'future', 'expired'])
def test_formal_health_consumer_exact_latest_db_clock_over_real_scram(fault):
    from datetime import timedelta
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from aos_api.aip_binding_formal_evaluator import (
        read_current_provider_health_fact, ProviderHealthFactUnavailable,
    )
    provider = dict(assetType='ProviderInstanceRevision', assetId='health-consumer-' + uuid4().hex,
                    revision=1, contentHash='a' * 64)
    with isolated_owner() as owner:
        owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        now = owner.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        observed, expires = now - timedelta(seconds=30), now + timedelta(minutes=5)
        if fault == 'future':
            observed, expires = now + timedelta(minutes=2), now + timedelta(minutes=5)
        if fault == 'expired':
            expires = now - timedelta(seconds=1)
        def insert(ref, at, until):
            owner.execute('INSERT INTO aip_provider_health_observation '
                '(org_id,project_id,observation_id,provider_ref,status,observed_at,expires_at) '
                "VALUES(%s,%s,%s,%s,'healthy',%s,%s)",
                (*SCOPE.key, uuid4().hex, Jsonb(ref), at, until))
        if fault != 'missing':
            insert(provider, observed, expires)
        if fault in {'revision', 'hash'}:
            newer = dict(provider)
            newer['revision' if fault == 'revision' else 'contentHash'] = 2 if fault == 'revision' else 'b' * 64
            insert(newer, now - timedelta(seconds=5), expires)
        if fault == 'ambiguous':
            insert(provider, observed, expires)
        owner.commit()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                if fault == 'none':
                    fact = read_current_provider_health_fact(conn, SCOPE, provider)
                    assert fact.provider_ref == provider and fact.status == 'healthy'
                    assert fact.epoch == 1
                    assert observed <= fact.checked_at < fact.expires_at
                    assert fact.checked_at <= conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                else:
                    with pytest.raises(ProviderHealthFactUnavailable):
                        read_current_provider_health_fact(conn, SCOPE, provider)


def test_formal_health_consumer_rejects_owner_connection_and_inexact_ref():
    from aos_api.aip_binding_formal_evaluator import (
        read_current_provider_health_fact, ProviderHealthFactUnavailable,
    )
    with isolated_owner() as owner:
        with pytest.raises(ProviderHealthFactUnavailable):
            read_current_provider_health_fact(owner, SCOPE, dict(assetType='ProviderInstanceRevision', assetId='inexact'))
        with pytest.raises(ProviderHealthFactUnavailable):
            read_current_provider_health_fact(owner, SCOPE, dict(assetType='ProviderInstanceRevision',
                assetId='exact', revision=1, contentHash='a' * 64))


@pytest.mark.parametrize('fault', ['missing_revision', 'bool_revision', 'unknown_field', 'canary'])
def test_formal_health_consumer_admission_rejects_before_epoch_side_effect(fault):
    from uuid import uuid4
    from aos_api.aip_binding_formal_evaluator import (
        read_current_provider_health_fact, ProviderHealthFactUnavailable,
    )
    provider = dict(assetType='ProviderInstanceRevision', assetId='health-rejected-' + uuid4().hex,
                    revision=1, contentHash='a' * 64)
    with isolated_owner() as owner:
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                if fault == 'missing_revision':
                    provider.pop('revision')
                elif fault == 'bool_revision':
                    provider['revision'] = True
                elif fault == 'unknown_field':
                    provider['ready'] = True
                else:
                    conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                with pytest.raises(ProviderHealthFactUnavailable):
                    read_current_provider_health_fact(conn, SCOPE, provider)
        assert owner.execute('SELECT count(*) AS n FROM aip_provider_health_epoch WHERE provider_id=%s',
                             (provider['assetId'],)).fetchone()['n'] == 0


@pytest.mark.parametrize('mode', ['shared_blocks_writer', 'snapshot_conflict'])
def test_formal_health_consumer_preserves_original_concurrent_fence(mode):
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    from aos_api.aip_binding_formal_evaluator import read_current_provider_health_fact
    provider = dict(assetType='ProviderInstanceRevision', assetId='health-concurrent-' + uuid4().hex,
                    revision=1, contentHash='a' * 64)
    with isolated_owner() as owner:
        def append():
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
            owner.execute('INSERT INTO aip_provider_health_observation '
                '(org_id,project_id,observation_id,provider_ref,status,observed_at,expires_at) '
                "VALUES(%s,%s,%s,%s,'healthy',clock_timestamp(),clock_timestamp()+interval '5 minutes')",
                (*SCOPE.key, uuid4().hex, Jsonb(provider)))
        append()
        owner.commit()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                if mode == 'shared_blocks_writer':
                    assert read_current_provider_health_fact(conn, SCOPE, provider).epoch == 1
                    owner.execute("SET LOCAL lock_timeout='100ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        append()
                    owner.rollback()
                else:
                    # Factory identity check has established the original SERIAL snapshot.
                    append()
                    owner.commit()
                    with pytest.raises(psycopg.errors.SerializationFailure) as error:
                        read_current_provider_health_fact(conn, SCOPE, provider)
                    assert error.value.sqlstate == '40001'
            if mode == 'shared_blocks_writer':
                append()
                owner.commit()
