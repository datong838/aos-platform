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


def assert_signed_source_budget_joint_transaction(source_request, loader, release_policy,
                                                  caller, issuer_factory, https_signer):
    """Real signed inputs in one native transaction; no full-command completion claim."""
    import json
    from pathlib import Path
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_license_source_authority import (
        _prepare_formal_source_approvals, read_formal_license_source_facts,
    )
    from aos_api.aip_budget_cost_runtime import (
        _prepare_formal_budget_approval, read_formal_budget_fact,
    )
    from tests.aip.test_budget_cost_consumer_pg import approved, consume
    from tests.aip.test_budget_cost_configuration_pg import derive

    maker, checker, proposal, saved, decision = approved(issuer_factory, https_signer)
    with caller() as consumer:
        activated = consume(consumer, saved, decision)
        configured = derive(consumer, saved, decision)
    source = FormalExactRef(assetType='EvidenceBundleRevision',
        assetId=source_request.source.resource_id, revision=source_request.source.revision,
        contentHash=source_request.source.content_hash)
    budget = FormalExactRef(assetType='BudgetRevision', assetId=activated['resourceId'],
        revision=activated['revision'], contentHash=activated['contentHash'])
    price = FormalExactRef.model_validate(configured['receipt']['priceRef'])
    provider = FormalExactRef.model_validate(proposal.basis.provider.model_dump(by_alias=True))
    tables = ('aip_capability_binding', 'aip_agent_registry_receipt',
              'aip_binding_evaluation_proof', 'aip_budget_reservation',
              'aip_model_eval_budget_reservation', 'aip_model_capacity_reservation')
    with isolated_owner() as owner:
        def snapshot():
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
            counts = {table: owner.execute(f'SELECT count(*) AS n FROM public.{table}').fetchone()['n']
                      for table in tables}
            fence = owner.execute('SELECT version FROM public.aip_budget_cost_runtime_fence '
                'WHERE org_id=%s AND project_id=%s AND budget_id=%s',
                (*SCOPE.key, budget.asset_id)).fetchone()['version']
            owner.rollback()
            return {'counts': counts, 'budget_fence': fence}
        before = snapshot()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                transaction = conn.execute('SELECT pg_current_xact_id()::text AS id').fetchone()['id']
                discovered, approvals = _prepare_formal_source_approvals(conn, SCOPE, [source])
                receipt, row, original = _prepare_formal_budget_approval(conn, SCOPE, budget)
                source_subjects = {subject for _, _, approved_ref, source_maker in discovered
                    for subject in (source_maker, approvals[approved_ref.resource_id][1]['actor_id'])}
                budget_subjects = {original.maker_subject, original.checker_subject}
                subjects = sorted(source_subjects | budget_subjects)
                members = conn.execute('SELECT subject,role FROM public.meta_membership '
                    'WHERE org_id=%s AND project_id=%s AND subject=ANY(%s) ORDER BY subject FOR SHARE',
                    (*SCOPE.key, subjects)).fetchall()
                assert [member['subject'] for member in members] == subjects
                assert all(member['role'].lower() == 'owner' for member in members
                           if member['subject'] in source_subjects)
                assert all(member['role'].lower() in {'owner', 'admin'} for member in members
                           if member['subject'] in budget_subjects)
                sources = read_formal_license_source_facts(conn=conn, scope=SCOPE,
                    source_refs=[source], installation_id=source_request.installation_id,
                    installation_revision=source_request.installation_revision,
                    installation_etag=source_request.installation_etag,
                    loader=loader, release_policy=release_policy)
                cost = read_formal_budget_fact(conn=conn, scope=SCOPE, budget_ref=budget,
                    price_ref=price, provider_ref=provider)
                assert len(sources) == 1 and sources[0].request == source_request
                assert {member['subject'] for member in sources[0].owners} == source_subjects
                assert budget_subjects == {maker.subject, checker.subject}
                assert cost.decision_id == decision['decisionId']
                assert receipt['result_ref']['proposalId'] == row['proposal_id'] == saved['proposalId']
                assert sources[0].checked_at < sources[0].valid_until
                assert cost.checked_at < cost.valid_until
                assert conn.execute('SELECT pg_current_xact_id()::text AS id').fetchone()['id'] == transaction
                proof = {'database': conn.info.dbname, 'port': conn.info.port,
                    'backend_pid': conn.info.backend_pid, 'transaction_id': transaction,
                    'real_scram': conn.pgconn.used_password,
                    'source_receipt': sources[0].source.receipt_id,
                    'budget_activation_receipt': cost.activation_receipt_id,
                    'budget_decision': cost.decision_id, 'members': subjects,
                    'source_owner_count': len(source_subjects),
                    'source_valid_until': sources[0].valid_until.isoformat(),
                    'budget_valid_until': cost.valid_until.isoformat()}
        after = snapshot()
        assert before == after
        proof.update(before=before, after=after,
            scope='Signed Growth 1.13 Source/Budget joint inputs only; full eight-fact command pending',
            business_first_chain_passed=False)
        evidence = Path(__file__).resolve().parents[4] / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob90/implementation/joint-input-facts.json'
        evidence.write_text(json.dumps(proof, indent=2) + '\n')


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



def test_original_eval_contract_missing_dependencies_are_business_blockers():
    """Actual SCRAM original reader; absent references never imply READY."""
    from uuid import uuid4
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.tenant_scope import TenantScope
    identity = 'b90-missing-eval-' + uuid4().hex
    def ref(kind):
        return {'resourceType': kind, 'resourceId': identity, 'revision': 1, 'contentHash': 'a' * 64}
    row = {'suite_ref': ref('EvalSuiteRevision'), 'publication_ref': ref('PublicationEvent'),
           'release_gate_ref': None}
    with isolated_owner() as owner:
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                blockers = AipProductionContractStore()._eval_blockers(conn, SCOPE, row)
                assert {item.code for item in blockers} == {
                    'EVAL_SUITE_MISSING', 'EVAL_PUBLICATION_MISSING', 'EVAL_GATE_MISSING'}
                for table in ('aip_eval_suite_revision', 'aip_publication_event'):
                    assert conn.execute('SELECT has_table_privilege(current_user,%s,\'SELECT\') AS allowed',
                        ('public.' + table,)).fetchone()['allowed']
                    assert not conn.execute('SELECT has_table_privilege(current_user,%s,\'UPDATE\') AS allowed',
                        ('public.' + table,)).fetchone()['allowed']
            with factory(TenantScope('dev-org', 'dev-project')) as conn:
                for table in ('aip_eval_suite_revision', 'aip_publication_event'):
                    assert conn.execute(f'SELECT count(*) AS n FROM public.{table}').fetchone()['n'] == 0


def test_formal_eval_contract_rejects_frozen_maintenance_fault_without_business_writes():
    """Corrupt frozen fixture, never a legitimate freeze or readiness positive."""
    from uuid import uuid4
    from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
    from aos_api.aip_production_contracts import CreateEvalContractRequest, BriefLifecycle
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    identity = 'b90-corrupt-frozen-' + uuid4().hex
    body = CreateEvalContractRequest(
        suiteRef={'resourceType': 'EvalSuiteRevision', 'resourceId': identity,
                  'revision': 1, 'contentHash': 'a' * 64},
        artifactSchemaRef={'resourceType': 'Schema', 'resourceId': identity,
                           'revision': '1', 'authority': 'aip'},
        severityThresholds={'critical': 1.0}, gatePolicy={'mode': 'all'},
        returnMapping={'critical': 'draft'}, overridePolicy={'allowed': False})
    content_hash = canonical_hash(body.model_dump(mode='json', by_alias=True))
    exact = FormalExactRef(assetType='EvalContractRevision', assetId=identity,
        revision=1, contentHash=content_hash)
    tables = ('aip_capability_binding', 'aip_agent_registry_receipt', 'aip_binding_evaluation_proof')
    with isolated_owner() as owner:
        owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','maintenance-negative') ON CONFLICT DO NOTHING")
        owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','maintenance-negative') ON CONFLICT DO NOTHING")
        owner.execute('INSERT INTO aip_eval_contract_head(org_id,project_id,contract_id,current_revision,version) '
            'VALUES(%s,%s,%s,1,1)', (*SCOPE.key, identity))
        AipProductionContractStore()._insert_eval(owner, SCOPE, identity, 1,
            'maintenance-negative', body, content_hash, BriefLifecycle.FROZEN)
        owner.commit()
        def snapshots():
            return [owner.execute(f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),"
                f"'[]'::jsonb) AS value FROM public.{table} t").fetchone()['value'] for table in tables]
        before = snapshots()
        owner.commit()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                original = AipProductionContractStore().get_eval_contract(SCOPE, identity, 1, conn=conn)
                assert original.lifecycle.value == 'frozen'
                assert original.readiness.value == 'blocked' and original.blockers
                from aos_api.aip_binding_formal_evaluator import (
                    _read_formal_eval_contract, FormalBindingEvaluationBlocked)
                with pytest.raises(FormalBindingEvaluationBlocked,
                        match='CURRENT_READY_FROZEN_EVAL_CONTRACT_REQUIRED'):
                    _read_formal_eval_contract(conn, SCOPE, exact)
        assert snapshots() == before


def assert_formal_signed_source_consumer(request, loader, release_policy):
    """Original signed Source/Proposal/OIDC approval/issuer, actual evaluator SCRAM."""
    from uuid import uuid4
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from psycopg.types.json import Jsonb
    from aos_api.aip_license_source_authority import read_formal_license_source_facts, LicenseSourceUnavailable
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from tests.aip.test_aip_license_source_authority_pg import raw_revoke, wait_blocked
    source_ref = FormalExactRef(assetType='EvidenceBundleRevision', assetId=request.source.resource_id,
        revision=request.source.revision, contentHash=request.source.content_hash)
    with isolated_owner() as owner:
        def scope():
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        def counts():
            return tuple(owner.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                for table in ('aip_license_source_issuance','aip_agent_registry_receipt','aip_binding_evaluation_proof'))
        before = counts()
        owner.commit()
        with _temporary_fixed_evaluator_login(owner) as factory:
            args = dict(scope=SCOPE, source_refs=[source_ref], installation_id=request.installation_id,
                installation_revision=request.installation_revision, installation_etag=request.installation_etag,
                loader=loader, release_policy=release_policy)
            with factory(SCOPE) as conn:
                from aos_api.aip_license_source_authority import _prepare_formal_source_approvals
                discovered, approvals = _prepare_formal_source_approvals(conn, SCOPE, args['source_refs'])
                assert len(discovered) == 1 and len(approvals) == 1
                assert all('actor_id' in event for _, event in approvals.values())
                facts = read_formal_license_source_facts(conn=conn, **args)
                assert {owner['subject'] for owner in facts[0].owners} == {
                    subject for _, _, approved, maker in discovered
                    for subject in (maker, approvals[approved.resource_id][1]['actor_id'])}
                assert len(facts) == 1
                fact = facts[0]
                assert fact.source.source.resource_id == request.source.resource_id
                assert fact.request == request and len(fact.owners) == 2
                assert fact.source.owner_authorization_ref['approvalEventId'] == fact.approval_event_id
                assert fact.valid_until <= fact.source.expires_at
                assert fact.authorization == 'FORMAL_SOURCE_FACT_ONLY_NO_START'
                from dataclasses import replace
                from aos_api.aip_binding_formal_evaluator import _source_proof_fact
                payload = _source_proof_fact(source_ref, fact)
                assert payload['epoch'] == fact.source.epoch
                assert payload['installationId'] == fact.source.installation_id
                assert payload['installationEtag'] == fact.source.installation_etag
                assert payload['ownerAuthorizationRef'] == fact.source.owner_authorization_ref
                assert payload['policyRef'] == fact.source.policy_ref
                assert payload['sourceRequestHash'] == fact.source_request_hash
                def proof_hash(value):
                    return conn.execute("SELECT encode(public.digest(convert_to("
                        "public.canonical_asset_registry_jsonb(%s::jsonb),'UTF8'),'sha256'),'hex') AS hash",
                        (Jsonb(value),)).fetchone()['hash']
                baseline_hash = proof_hash(payload)
                # Actual signed fact, synthetic copies: hash sensitivity only.
                for changed in (
                    replace(fact.source, epoch=fact.source.epoch + 1),
                    replace(fact.source, installation_etag=fact.source.installation_etag + 1),
                    replace(fact.source, owner_authorization_ref={'changed': True}),
                    replace(fact.source, policy_ref={'changed': True}),
                ):
                    assert proof_hash(_source_proof_fact(source_ref, replace(fact, source=changed))) != baseline_hash
            assert counts() == before
            owner.commit()
            for changes in (
                {'source_refs': [source_ref.model_copy(update={'content_hash':'f'*64})]},
                {'installation_etag':request.installation_etag+1},
                {'installation_revision':request.installation_revision+1},
                {'installation_etag':True}, {'source_refs':[source_ref,source_ref]},
            ):
                with factory(SCOPE) as conn:
                    with pytest.raises(LicenseSourceUnavailable):
                        read_formal_license_source_facts(conn=conn, **{**args, **changes})
            with factory(SCOPE) as conn:
                conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                with pytest.raises(BindingEvaluatorConnectionBlocked):
                    read_formal_license_source_facts(conn=conn, **args)
            for subject in (entry['subject'] for entry in fact.owners):
                scope()
                owner.execute("UPDATE meta_membership SET role='admin' WHERE org_id=%s AND project_id=%s AND subject=%s",
                              (*SCOPE.key,subject))
                owner.commit()
                try:
                    with factory(SCOPE) as conn:
                        with pytest.raises(LicenseSourceUnavailable, match='BOTH_CURRENT_OWNERS_REQUIRED'):
                            read_formal_license_source_facts(conn=conn, **args)
                finally:
                    scope()
                    owner.execute("UPDATE meta_membership SET role='owner' WHERE org_id=%s AND project_id=%s AND subject=%s",
                                  (*SCOPE.key,subject))
                    owner.commit()
            # Native reader holds the original Owner/install/Source fences.
            pids = Queue()
            def writer(kind):
                with isolated_owner() as other:
                    other.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                    pids.put(other.info.backend_pid)
                    try:
                        if kind == 'owner':
                            other.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                                (*SCOPE.key,fact.owners[0]['subject']))
                        elif kind == 'installation':
                            other.execute('SELECT installation_id FROM bundle_installation WHERE org_id=%s AND project_id=%s '
                                'AND installation_id=%s FOR UPDATE', (*SCOPE.key,request.installation_id))
                        else:
                            raw_revoke(other, request.source.resource_id, content_hash=request.source.content_hash)
                    finally:
                        other.rollback()
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = []
                try:
                    with factory(SCOPE) as conn:
                        read_formal_license_source_facts(conn=conn, **args)
                        futures = [pool.submit(writer, kind) for kind in ('owner','installation','revoke')]
                        writer_pids = [pids.get(timeout=5) for _ in futures]
                        owner.commit()
                        wait_blocked(owner, writer_pids, conn.info.backend_pid, futures)
                        owner.rollback()
                    for future in futures:
                        future.result(timeout=8)
                finally:
                    for future in futures:
                        future.result(timeout=8)
            assert counts() == before
            owner.commit()
            # Historical maintenance faults are never positive license authority.
            # Immutable injected rows remain only in this disposable database.
            scope()
            original = owner.execute('SELECT * FROM aip_license_source_issuance WHERE issuance_id=%s',
                                     (fact.source.issuance_id,)).fetchone()
            owner.commit()
            for mode in ('legacy_schema', 'wrong_original_receipt'):
                injected = {**original, 'issuance_id':'b90-fault-'+uuid4().hex}
                if mode == 'legacy_schema':
                    injected['owner_authorization_ref'] = {'test':'legacy fixture'}
                scope()
                owner.execute(sql.SQL('INSERT INTO aip_license_source_issuance ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier, injected)),
                    sql.SQL(',').join(sql.Placeholder() for _ in injected)),
                    [Jsonb(value) if isinstance(value,dict) else value for value in injected.values()])
                owner.execute('UPDATE aip_license_source_head SET issuance_id=%s WHERE org_id=%s AND project_id=%s '
                    'AND bundle_id=%s AND revision=%s',
                    (injected['issuance_id'],*SCOPE.key,request.source.resource_id,request.source.revision))
                owner.commit()
                fault_before = counts()
                owner.commit()
                try:
                    with factory(SCOPE) as conn:
                        expected = 'ORIGINAL_AUTHORIZATION_REQUIRED' if mode == 'legacy_schema' else 'ORIGINAL_RECEIPT_DRIFT'
                        with pytest.raises(LicenseSourceUnavailable, match=expected):
                            read_formal_license_source_facts(conn=conn, **args)
                    assert counts() == fault_before
                    owner.commit()
                finally:
                    scope()
                    owner.execute('UPDATE aip_license_source_head SET issuance_id=%s WHERE org_id=%s AND project_id=%s '
                        'AND bundle_id=%s AND revision=%s',
                        (original['issuance_id'],*SCOPE.key,request.source.resource_id,request.source.revision))
                    owner.commit()
            assert counts() == (before[0]+2,before[1],before[2])
            import json
            from pathlib import Path
            evidence = Path(__file__).resolve().parents[4] / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob90/implementation/source-consumer-facts.json'
            evidence.write_text(json.dumps({
                'database':owner.info.dbname,'port':owner.info.port,
                'original_source_issuance':fact.source.issuance_id,
                'original_approval_event':fact.approval_event_id,
                'original_receipt':fact.source.receipt_id,
                'owner_count':len(fact.owners),'source_epoch':fact.source.epoch,
                'checked_at':fact.checked_at.isoformat(),'valid_until':fact.valid_until.isoformat(),
                'positive_counts_before':before,'positive_counts_after':before,
                'fault_injected_immutable_rows':2,'final_counts':counts(),
                'real_scram':True,'writer_fences':['owner','installation','source_revoke'],
                'rejected':['wrong_hash','installation_etag','installation_revision','bool_etag',
                            'duplicate_ref','canary_guc','maker_demoted','checker_demoted',
                            'legacy_schema','wrong_original_receipt'],
                'scope':'Isolated original signed Source consumer only; complete evaluator pending',
            },indent=2)+'\n')


# Original HTTPS budget approval and SQL configuration producers, never price_for.
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer


@pytest.mark.parametrize('fault', ['none', 'hash', 'provider', 'budget_head', 'member', 'revoked', 'canary', 'snapshot_revoke', 'no_activation', 'exhausted', 'expired'])
def test_formal_budget_consumer_original_signed_configuration_no_fence_write(
        caller, issuer_factory, https_signer, fault):
    from tests.aip.test_budget_cost_consumer_pg import approved, consume
    from tests.aip.test_budget_cost_configuration_pg import derive
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    if fault == 'expired':
        from tests.aip.test_budget_cost_issuer_pg import prepared, command
        from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
        maker, checker, _, proposal, saved = prepared(window=8)
        decision = BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], checker, saved))
    else:
        maker, checker, proposal, saved, decision = approved(issuer_factory, https_signer)
    with caller() as conn:
        activated = consume(conn, saved, decision)
        configured = derive(conn, saved, decision)
    from aos_api.aip_budget_cost_runtime import read_formal_budget_fact
    def exact(kind, value):
        return FormalExactRef(assetType=kind, assetId=value['assetId'],
            revision=value['revision'], contentHash=value['contentHash'])
    budget = FormalExactRef(assetType='BudgetRevision', assetId=activated['resourceId'],
        revision=activated['revision'], contentHash=activated['contentHash'])
    if fault == 'no_activation':
        budget = budget.model_copy(update={'asset_id': 'missing-' + proposal.target.budget_id})
    if fault == 'exhausted':
        from aos_api.db import connect_serializable
        from aos_api.aip_budget_cost_runtime import require_cost_risk
        from aos_api.aip_budget_reservation_contracts import BudgetExactRef
        from tests.aip.test_budget_cost_consumer_pg import ledger_hold
        policy = BudgetExactRef(resourceType='BudgetRevision', resourceId=activated['resourceId'],
            revision=activated['revision'], contentHash='sha256:' + activated['contentHash'])
        price_value = configured['receipt']['priceRef']
        pricing = BudgetExactRef(resourceType='ModelPriceSnapshotRevision', resourceId=price_value['assetId'],
            revision=price_value['revision'], contentHash='sha256:' + price_value['contentHash'])
        with connect_serializable(SCOPE) as conn:
            for _ in range(proposal.basis.max_requests):
                require_cost_risk(conn, SCOPE, policy, pricing, proposal.basis.per_request_risk_minor)
                ledger_hold(conn, proposal, policy, pricing)
            conn.commit()
    if fault == 'revoked':
        from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
        from tests.aip.test_budget_cost_issuer_pg import command
        BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], maker, saved,
            operation='revoke', decision=None, reason='formal-test-withdrawal'))
    with isolated_owner() as owner:
        if fault == 'member':
            owner.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                (*SCOPE.key, checker.subject))
        elif fault == 'budget_head':
            owner.execute('UPDATE aip_budget_head SET version=version+1 WHERE budget_id=%s',
                (proposal.target.budget_id,))
        owner.commit()
        if fault == 'hash':
            budget = budget.model_copy(update={'content_hash': '0' * 64})
        before = owner.execute('SELECT version FROM aip_budget_cost_runtime_fence WHERE budget_id=%s',
            (proposal.target.budget_id,)).fetchone()
        owner.rollback()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(SCOPE) as conn:
                provider = exact('ProviderInstanceRevision', proposal.basis.provider.model_dump(by_alias=True))
                if fault == 'provider':
                    provider = provider.model_copy(update={'content_hash': '0' * 64})
                if fault == 'none':
                    from aos_api.aip_budget_cost_runtime import _prepare_formal_budget_approval
                    receipt, proposal_row, original = _prepare_formal_budget_approval(conn, SCOPE, budget)
                    assert original.maker_subject == maker.subject
                    assert original.checker_subject == checker.subject
                    assert receipt['result_ref']['proposalId'] == proposal_row['proposal_id']
                if fault == 'canary':
                    conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                if fault == 'snapshot_revoke':
                    conn.execute('SELECT count(*) FROM public.aip_budget_cost_runtime_fence')
                    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
                    from tests.aip.test_budget_cost_issuer_pg import command
                    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], maker, saved,
                        operation='revoke', decision=None, reason='snapshot-test-withdrawal'))
                if fault == 'expired':
                    from time import sleep
                    args = dict(conn=conn, scope=SCOPE, budget_ref=budget,
                        price_ref=exact('ModelPriceSnapshotRevision', configured['receipt']['priceRef']),
                        provider_ref=provider)
                    fact = read_formal_budget_fact(**args)
                    now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    sleep(max(0, (fact.valid_until - now).total_seconds()) + .03)
                expected_error = (psycopg.errors.SerializationFailure if fault == 'snapshot_revoke' else
                    BindingEvaluatorConnectionBlocked if fault == 'canary' else ValueError)
                with pytest.raises(expected_error) if fault != 'none' else nullcontext():
                    fact = read_formal_budget_fact(conn=conn, scope=SCOPE, budget_ref=budget,
                        price_ref=exact('ModelPriceSnapshotRevision', configured['receipt']['priceRef']),
                        provider_ref=provider)
                    assert fact.decision_id == decision['decisionId']
                    assert fact.per_request_risk_minor == proposal.basis.per_request_risk_minor
                    assert fact.checked_at < fact.valid_until
        after = owner.execute('SELECT version FROM aip_budget_cost_runtime_fence WHERE budget_id=%s',
            (proposal.target.budget_id,)).fetchone()
        assert after == ({'version': before['version'] + 1} if fault == 'snapshot_revoke' else before)


@pytest.mark.parametrize('writer_kind', ['hold', 'revoke'])
def test_formal_budget_shared_authority_blocks_original_writer(caller, issuer_factory, https_signer, writer_kind):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from tests.aip.test_budget_cost_consumer_pg import approved, consume
    from tests.aip.test_budget_cost_configuration_pg import derive
    from tests.aip.test_aip_license_source_authority_pg import wait_blocked
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_budget_cost_runtime import read_formal_budget_fact, require_cost_risk
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.db import connect_serializable
    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
    from tests.aip.test_budget_cost_issuer_pg import command
    maker, _, proposal, saved, decision = approved(issuer_factory, https_signer)
    with caller() as conn:
        activated = consume(conn, saved, decision)
        configured = derive(conn, saved, decision)
    budget = FormalExactRef(assetType='BudgetRevision', assetId=activated['resourceId'],
        revision=activated['revision'], contentHash=activated['contentHash'])
    price = FormalExactRef.model_validate(configured['receipt']['priceRef'])
    provider = FormalExactRef.model_validate(proposal.basis.provider.model_dump(by_alias=True))
    pids = Queue()
    def writer():
        if writer_kind == 'hold':
            with connect_serializable(SCOPE) as conn:
                pids.put(conn.info.backend_pid)
                def old(ref):
                    return BudgetExactRef(resourceType=ref.asset_type, resourceId=ref.asset_id,
                        revision=ref.revision, contentHash='sha256:' + ref.content_hash)
                try:
                    require_cost_risk(conn, SCOPE, old(budget), old(price), proposal.basis.per_request_risk_minor)
                finally:
                    conn.rollback()
        else:
            @contextmanager
            def observed_factory(scope, read_only):
                with issuer_factory(scope, read_only) as conn:
                    pids.put(conn.info.backend_pid)
                    yield conn
            return BudgetCostIssuer(observed_factory).execute(command(https_signer[0], maker, saved,
                operation='revoke', decision=None, reason='blocked-issuer-withdrawal'))
    with isolated_owner() as owner:
        before = owner.execute('SELECT version FROM aip_budget_cost_runtime_fence WHERE budget_id=%s',
            (proposal.target.budget_id,)).fetchone()['version']
        owner.rollback()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with factory(SCOPE) as conn:
                    read_formal_budget_fact(conn=conn, scope=SCOPE, budget_ref=budget, price_ref=price, provider_ref=provider)
                    future = pool.submit(writer)
                    pid = pids.get(timeout=5)
                    owner.commit()
                    wait_blocked(owner, [pid], conn.info.backend_pid, [future])
                    owner.rollback()
                future.result(timeout=10)
        after = owner.execute('SELECT version FROM aip_budget_cost_runtime_fence WHERE budget_id=%s',
            (proposal.target.budget_id,)).fetchone()['version']
        assert after == before + (1 if writer_kind == 'revoke' else 0)


@pytest.mark.parametrize('order', ['budget_first', 'capacity_first'])
def test_formal_evaluator_capacity_budget_original_writer_lock_order(
        caller, issuer_factory, https_signer, order):
    """Actual mutual waits versus prelocking; the head is a coordination probe.

    The cost chain is original and signed. The isolated head has no revision or
    fake READY and cannot supply a Capacity fact or a formal evaluation proof.
    Every runtime writer rolls back, including its original fence increment.
    """
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from uuid import uuid4
    from threading import Event
    from pathlib import Path
    import json
    import time
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_budget_cost_runtime import read_formal_budget_fact, require_cost_risk
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.db import connect_serializable
    from tests.aip.test_budget_cost_consumer_pg import approved, consume
    from tests.aip.test_budget_cost_configuration_pg import derive
    from tests.aip.test_aip_license_source_authority_pg import wait_blocked

    _, _, proposal, saved, decision = approved(issuer_factory, https_signer)
    with caller() as consumer:
        activated = consume(consumer, saved, decision)
        configured = derive(consumer, saved, decision)
    budget = FormalExactRef(assetType='BudgetRevision', assetId=activated['resourceId'],
        revision=activated['revision'], contentHash=activated['contentHash'])
    price = FormalExactRef.model_validate(configured['receipt']['priceRef'])
    provider = FormalExactRef.model_validate(proposal.basis.provider.model_dump(by_alias=True))
    capacity = FormalExactRef(assetType='ModelCapacityPoolRevision',
        assetId='b90-lock-probe-' + uuid4().hex, revision=1, contentHash='a' * 64)
    head_sql = ('SELECT current_revision,version FROM public.aip_model_capacity_pool_head '
        'WHERE org_id=%s AND project_id=%s AND pool_id=%s')
    head_params = (*SCOPE.key, capacity.asset_id)
    pids = Queue()
    capacity_acquired = Event()

    def writer():
        with connect_serializable(SCOPE) as conn:
            pids.put(conn.info.backend_pid)
            try:
                assert conn.execute(head_sql + ' FOR SHARE', head_params).fetchone()
                capacity_acquired.set()
                def old(ref):
                    return BudgetExactRef(resourceType=ref.asset_type, resourceId=ref.asset_id,
                        revision=ref.revision, contentHash='sha256:' + ref.content_hash)
                require_cost_risk(conn, SCOPE, old(budget), old(price),
                    proposal.basis.per_request_risk_minor, provider_ref=old(provider))
                return 'validated'
            except Exception as exc:
                return exc
            finally:
                conn.rollback()

    with isolated_owner() as owner:
        owner.execute('INSERT INTO public.aip_model_capacity_pool_head '
            '(org_id,project_id,pool_id,current_revision,version) VALUES(%s,%s,%s,1,1)', head_params)
        owner.commit()
        def snapshot():
            counts = {table: owner.execute(f'SELECT count(*) AS n FROM public.{table}').fetchone()['n']
                for table in ('aip_capability_binding', 'aip_agent_registry_receipt',
                    'aip_binding_evaluation_proof', 'aip_budget_reservation',
                    'aip_model_eval_budget_reservation', 'aip_model_capacity_reservation')}
            fence = owner.execute('SELECT version FROM public.aip_budget_cost_runtime_fence '
                'WHERE org_id=%s AND project_id=%s AND budget_id=%s',
                (*SCOPE.key, budget.asset_id)).fetchone()['version']
            head = owner.execute(head_sql, head_params).fetchone()
            owner.rollback()
            return counts, fence, head
        before = snapshot()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with ThreadPoolExecutor(max_workers=2) as pool:
                with factory(SCOPE) as conn:
                    evaluator_pid = conn.info.backend_pid
                    native_scram = conn.pgconn.used_password
                    if order == 'capacity_first':
                        from aos_api.aip_binding_formal_evaluator import _prepare_formal_capacity_head
                        _prepare_formal_capacity_head(conn, SCOPE, capacity)
                    read_formal_budget_fact(conn=conn, scope=SCOPE, budget_ref=budget,
                        price_ref=price, provider_ref=provider)
                    other = pool.submit(writer)
                    writer_pid = pids.get(timeout=5)
                    wait_blocked(owner, [writer_pid], conn.info.backend_pid, [other])
                    owner.rollback()
                    if order == 'budget_first':
                        assert capacity_acquired.is_set()
                        def reverse_lock():
                            try:
                                conn.execute(head_sql + ' FOR UPDATE', head_params).fetchone()
                                return 'locked'
                            except Exception as exc:
                                return exc
                        reverse = pool.submit(reverse_lock)
                        end = time.monotonic() + .8
                        while time.monotonic() < end:
                            graph = owner.execute('SELECT pg_blocking_pids(%s) AS evaluator, '
                                'pg_blocking_pids(%s) AS writer',
                                (conn.info.backend_pid, writer_pid)).fetchone()
                            owner.rollback()
                            if writer_pid in graph['evaluator'] and conn.info.backend_pid in graph['writer']:
                                break
                            assert not reverse.done() and not other.done(), 'cycle ended before graph readback'
                            time.sleep(.01)
                        else:
                            pytest.fail('the expected two-sided original lock cycle was not observed')
                        result = reverse.result(timeout=6)
                        conn.rollback()
                        outcome = other.result(timeout=6)
                        errors = [value for value in (result, outcome) if isinstance(value, Exception)]
                        assert any(isinstance(value, psycopg.errors.DeadlockDetected)
                            or isinstance(value.__cause__, psycopg.errors.DeadlockDetected) for value in errors)
                        checked = {'two_sided_wait': graph, 'deadlock_detected': True}
                    else:
                        assert not capacity_acquired.is_set(), 'writer must wait before acquiring Capacity'
                        checked = {'writer_waits_on': owner.execute('SELECT pg_blocking_pids(%s) AS pids',
                            (writer_pid,)).fetchone()['pids'], 'deadlock_detected': False}
                        owner.rollback()
                        assert not other.done()
                        conn.rollback()
                        assert other.result(timeout=6) == 'validated'
        assert snapshot() == before
        evidence = Path(__file__).resolve().parents[4] / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob90/implementation'
        (evidence / f'capacity-budget-lock-{order}.json').write_text(json.dumps({
            'scope': 'isolated original signed Budget / Capacity-head coordination probe only',
            'database': owner.info.dbname, 'port': owner.info.port, 'order': order,
            'writer_pid': writer_pid, 'evaluator_pid': evaluator_pid,
            'native_scram': native_scram, 'observed': checked, 'before': before, 'after': snapshot(),
            'capacity_fact_proven': False, 'complete_evaluator_passed': False,
            'business_first_chain_passed': False, 'current_database_accessed': False}, indent=2) + '\n')


@pytest.mark.parametrize('fault', ['missing', 'stale', 'kind', 'strict_revision', 'wrapper', 'canary'])
def test_formal_capacity_prelock_rejects_scope_identity_and_current_head(fault):
    from uuid import uuid4
    from types import SimpleNamespace
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_binding_formal_evaluator import (
        _prepare_formal_capacity_head, FormalCapacityUnavailable,
    )
    from aos_api.tenant_scope import TenantScope
    capacity = FormalExactRef(assetType='ModelCapacityPoolRevision',
        assetId='b90-lock-fault-' + uuid4().hex, revision=1, contentHash='a' * 64)
    scope = TenantScope('dev-org', 'dev-project') if fault == 'canary' else SCOPE
    with isolated_owner() as owner:
        if fault != 'missing':
            owner.execute('INSERT INTO public.aip_model_capacity_pool_head '
                '(org_id,project_id,pool_id,current_revision,version) VALUES(%s,%s,%s,%s,1)',
                (*SCOPE.key, capacity.asset_id, 2 if fault == 'stale' else 1))
            owner.commit()
        if fault == 'kind':
            capacity = capacity.model_copy(update={'asset_type': 'ProviderInstanceRevision'})
        elif fault == 'strict_revision':
            capacity = capacity.model_copy(update={'revision': True})
        error = BindingEvaluatorConnectionBlocked if fault in {'wrapper', 'canary'} else FormalCapacityUnavailable
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(scope) as conn:
                with pytest.raises(error):
                    _prepare_formal_capacity_head(SimpleNamespace(native=conn) if fault == 'wrapper' else conn,
                        scope, capacity)
        row = owner.execute('SELECT current_revision,version FROM public.aip_model_capacity_pool_head '
            'WHERE org_id=%s AND project_id=%s AND pool_id=%s', (*SCOPE.key, capacity.asset_id)).fetchone()
        assert row == (None if fault == 'missing' else {'current_revision': 2 if fault == 'stale' else 1, 'version': 1})


@pytest.mark.parametrize('fault', ['missing_binding', 'dev_actor', 'wrapper', 'canary', 'strict_body'])
def test_complete_formal_command_rejects_before_any_business_write(https_signer, tmp_path, fault):
    """Original TLS/OIDC and native admission, never eight-fact positive proof."""
    from types import SimpleNamespace
    from uuid import uuid4
    from pydantic import ValidationError
    from aos_api.auth import resolve_principal, Principal
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_binding_formal_evaluator_contracts import FormalBindingEvaluationRequest
    from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from tests.aip.test_binding_formal_evaluator_contracts import request_body
    subject = 'b90-command-actor-' + uuid4().hex
    principal = resolve_principal(token=https_signer[0](subject))
    assert principal.token_kind == 'oidc'
    request = FormalBindingEvaluationRequest.model_validate(request_body())
    scope = TenantScope('dev-org', 'dev-project') if fault == 'canary' else SCOPE
    root = tmp_path / 'empty-allowlisted-material'
    root.mkdir(mode=0o700)
    # No trust or Source positive is claimed: failure precedes material access.
    loader = ManifestLoader({'test-only': root})
    policy = ReleasePolicy(trust_roots=None)
    tables = ('aip_capability_binding', 'aip_agent_registry_receipt', 'aip_binding_evaluation_proof',
        'aip_budget_cost_runtime_fence', 'aip_model_capacity_reservation', 'aip_license_source_issuance',
        'aip_provider_health_epoch')
    with isolated_owner() as owner:
        def counts():
            result = {table: owner.execute(f'SELECT count(*) AS n FROM public.{table}').fetchone()['n']
                for table in tables}
            owner.rollback()
            return result
        before = counts()
        with _temporary_fixed_evaluator_login(owner) as factory:
            with factory(scope) as conn:
                from aos_api.aip_binding_formal_evaluator import (
                    evaluate_binding_in_transaction, FormalBindingEvaluationBlocked,
                )
                if fault == 'dev_actor':
                    principal = Principal(subject, *SCOPE.key, token_kind='dev')
                if fault == 'strict_body':
                    request = request.model_copy(update={'expected_version': True})
                expected = (AipAgentRegistryNotFound if fault == 'missing_binding' else
                    ValidationError if fault == 'strict_body' else
                    BindingEvaluatorConnectionBlocked if fault in {'wrapper', 'canary'} else
                    FormalBindingEvaluationBlocked)
                with pytest.raises(expected):
                    evaluate_binding_in_transaction(
                        SimpleNamespace(native=conn) if fault == 'wrapper' else conn,
                        scope, 'b90-never-existing-' + uuid4().hex, request, principal,
                        idempotency_key='b90-full-' + uuid4().hex,
                        loader=loader, release_policy=policy)
                conn.rollback()
        assert counts() == before
        assert https_signer[1], 'OIDC must actually fetch the isolated HTTPS JWKS'
