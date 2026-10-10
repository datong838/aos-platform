"""New admission fact boundary on retained native lab; no admission success claim."""
import json
import hashlib
import os
import re
import subprocess
from pathlib import Path

import psycopg
import pytest

from aos_api.aip_shared_parent_atomic_admission import FUNCTION, shared_parent_original_fact_statements
from aos_api.aip_physical_capacity_occupation_authority import OWNER, PLAN_FACT, occupation_plan_risk_statements


def test_final_intent_comparison_retains_original_authority_and_rows():
    from aos_api import aip_shared_parent_atomic_admission as api
    statements = api.shared_parent_final_intent_validation_statements()
    body = statements[0]
    assert not re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b', body, re.I)
    for check in ('SHARED_ADMISSION_INTENT_NATIVE_CALLER_REQUIRED',
                  'SHARED_ADMISSION_TARGET_INTENT_REPLAY_CONFLICT',
                  'SHARED_ADMISSION_JUDGE_DEPENDENCY_REPLAY_CONFLICT',
                  'SHARED_ADMISSION_INTENT_CURRENT_AFTER_WAITS_REQUIRED',
                  'capacity_occupation_eval_case_fact', 'read_shared_parent_pending_origin'):
        assert check in body
    assert api._physical.occupation_input_bytes_validation_sql() in body
    root = Path(__file__).resolve().parents[4]
    frozen = json.loads((root / '.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/final-reader-closure-r1/result.json').read_text())
    producer = next(s for s in api.shared_parent_initial_intent_statements()
                    if s.startswith('CREATE FUNCTION ' + api.INITIAL_INTENT.split('(')[0]))
    assert hashlib.sha256(producer.encode()).hexdigest() == frozen['sql_hashes'][api.INITIAL_INTENT.split('(')[0]]


@pytest.mark.parametrize('drift', ['boundary', 'new_writer'])
def test_final_intent_comparison_rejects_producer_drift(monkeypatch, drift):
    from aos_api import aip_shared_parent_atomic_admission as api
    original = api.shared_parent_initial_intent_statements
    def changed():
        values = list(original())
        for i, sql in enumerate(values):
            if sql.startswith('CREATE FUNCTION ' + api.INITIAL_INTENT.split('(')[0]):
                values[i] = (sql.replace('INSERT INTO ' + api.PHYSICAL_SCHEMA + '.target_intent', 'INSERT  INTO ' + api.PHYSICAL_SCHEMA + '.target_intent', 1)
                             if drift == 'boundary' else sql.replace('RETURN jsonb_build_object', 'DELETE FROM extra_table; RETURN jsonb_build_object', 1))
        return tuple(values)
    monkeypatch.setattr(api, 'shared_parent_initial_intent_statements', changed)
    with pytest.raises(ValueError, match='SHARED_ADMISSION_FINAL_INTENT_'):
        api.shared_parent_final_intent_validation_statements()


def test_native_final_intent_comparison_closed_and_rollback(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for generator in (api.shared_parent_admission_origin_statements,
                      api.shared_parent_admission_certificate_set_statements,
                      api.shared_parent_admission_storage_statements,
                      api.shared_parent_pending_origin_lookup_statements,
                      api.shared_parent_physical_obligation_statements,
                      api.shared_parent_initial_intent_statements,
                      api.shared_parent_final_intent_validation_statements):
        for statement in generator():
            native.execute(statement)
    row = native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.FINAL_INTENT,)).fetchone()
    assert row == (OWNER, True, ['search_path=pg_catalog'])
    assert not native.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p, LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE')", (api.FINAL_INTENT,)).fetchone()[0]
    for role in ('aos_runtime', 'aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, api.FINAL_INTENT)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_INTENT_NATIVE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.verify_shared_parent_final_intents(' + ','.join(['NULL'] * 18) + ')')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)', (api.FINAL_INTENT,)).fetchone()[0] is None
    native.rollback()


def test_certificate_waits_precede_complete_signature_validation():
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api import aip_shared_parent_certificate_prepare as original
    lock_phase = api.shared_parent_admission_certificate_lock_sql()
    full = original.shared_parent_certificate_claim_sql()
    assert 'FOR SHARE OF e' in lock_phase
    assert 'SHARED_CERTIFICATE_COMPLETE_SET_REQUIRED' in lock_phase
    assert 'SHARED_CERTIFICATE_PREPUBLISHED_ROOT_REQUIRED' in lock_phase
    assert 'verify_model_shared_parent_certificate_signature' not in lock_phase
    body = next(s for s in api.shared_parent_admission_certificate_set_statements()
                if s.startswith('CREATE FUNCTION '))
    assert body.count(full) == 1
    assert body.count(api.shared_parent_admission_certificate_validation_sql()) == 1
    before, after = body.split(lock_phase, 1)
    assert api.ORIGIN.split('(')[0] + '(' in before
    assert after.index(api.ORIGIN.split('(')[0] + '(') < after.index(full)
    assert 'SHARED_ADMISSION_CERTIFICATE_ORIGIN_CHANGED' in after


def test_certificate_phase_boundary_drift_fails_closed(monkeypatch):
    from aos_api import aip_shared_parent_atomic_admission as api
    monkeypatch.setattr(api._certificate, 'shared_parent_certificate_claim_sql',
                        lambda: 'unrecognized or missing original lock phase')
    with pytest.raises(ValueError, match='SHARED_CERTIFICATE_LOCK_PHASE_BOUNDARY_REQUIRED'):
        api.shared_parent_admission_certificate_set_statements()


@pytest.fixture
def native():
    path = os.environ.get('AOS_SHARED_ADMISSION_LAB_MANIFEST')
    if not path:
        pytest.skip('explicit retained isolated lab manifest required')
    lab = json.loads(Path(path).read_text())
    item = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']]))[0]
    assert item['Id'] == lab['container_id'] and item['Image'] == lab['image'] and item['State']['Running']
    database = os.environ['AOS_SHARED_ADMISSION_LAB_DATABASE']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app', dbname=database,
                         passfile=lab['passfile']) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        assert conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == lab['cluster']
        assert conn.execute('SELECT to_regprocedure(%s)', (FUNCTION,)).fetchone()[0] is None
        before = conn.execute("SELECT p.oid::regprocedure::text,p.prosrc,p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_physical_capacity_occupation_private' OR p.proname LIKE 'prepare_capacity%%' ORDER BY 1").fetchall()
        for statement in shared_parent_original_fact_statements():
            conn.execute(statement)
        yield conn
        conn.execute('RESET ROLE')
        conn.execute('RESET SESSION AUTHORIZATION')
        after = conn.execute("SELECT p.oid::regprocedure::text,p.prosrc,p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_physical_capacity_occupation_private' OR p.proname LIKE 'prepare_capacity%%' ORDER BY 1").fetchall()
        assert after == before
        conn.rollback()
        assert conn.execute('SELECT to_regprocedure(%s)', (FUNCTION,)).fetchone()[0] is None
        conn.rollback()


def test_native_owner_search_path_and_no_direct_runtime_privilege(native):
    row = native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (FUNCTION,)).fetchone()
    assert row == (OWNER, True, ['search_path=pg_catalog'])
    assert native.execute('SELECT has_function_privilege(%s,%s,%s)', ('aos_runtime', FUNCTION, 'EXECUTE')).fetchone()[0] is False
    assert native.execute('SELECT has_function_privilege(%s,%s,%s)', (OWNER, FUNCTION, 'EXECUTE')).fetchone()[0] is True


def test_original_fact_dependency_is_native_exact_and_callable_by_owner(native):
    statement = next(x for x in occupation_plan_risk_statements() if x.startswith('CREATE FUNCTION ' + PLAN_FACT.split('(')[0] + '('))
    body = re.search(r'\$planfact\$(.*?)\$planfact\$', statement, re.S)[1]
    row = native.execute('SELECT prosrc,pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (PLAN_FACT,)).fetchone()
    assert row == (body, 'aos_runtime', True, ['search_path=pg_catalog'])
    assert native.execute('SELECT has_function_privilege(%s,%s,%s)', (OWNER, PLAN_FACT, 'EXECUTE')).fetchone()[0] is True


@pytest.mark.parametrize('org,timezone', [('org-org', 'UTC'), ('dev-org', 'UTC'), ('org-org', 'Asia/Shanghai')])
def test_native_admin_session_rejected_with_positive_or_canary_scope(native, org, timezone):
    # This test-owned wrapper exercises the internal owner boundary, never an
    # installation or trusted production caller. Everything rolls back.
    wrapper = 'public.test_shared_admission_fact_boundary'
    native.execute(f"CREATE FUNCTION {wrapper}() RETURNS jsonb LANGUAGE SQL SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.read_shared_parent_admission_original_facts(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)'")
    native.execute(f'ALTER FUNCTION {wrapper}() OWNER TO {OWNER}')
    native.execute(f'REVOKE ALL ON FUNCTION {wrapper}() FROM PUBLIC')
    native.execute(f'GRANT EXECUTE ON FUNCTION {wrapper}() TO aos_runtime')
    native.execute('SELECT set_config(%s,%s,true)', ('aos.org_id', org))
    native.execute("SELECT set_config('aos.project_id','dev-project',true)")
    native.execute('SELECT set_config(%s,%s,true)', ('TimeZone', timezone))
    # Test-owned admin -> owner exercises rejection before original facts.
    # It does not establish a formal authenticated occupation caller, nor
    # prove independent per-field validation under an authorized caller.
    native.execute(f'SET LOCAL ROLE {OWNER}')
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_ORIGINAL_FACT_CALLER_REQUIRED'):
        with native.transaction():
            native.execute(f'SELECT {wrapper}()')


def test_original_login_cannot_gain_runtime_role(native):
    assert native.execute("SELECT pg_has_role('aos_provider_capacity_occupation','aos_runtime','MEMBER')").fetchone()[0] is False
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='permission denied to set role'):
        with native.transaction():
            native.execute('SET SESSION AUTHORIZATION aos_provider_capacity_occupation')
            native.execute('SET LOCAL ROLE aos_runtime')


def test_fact_artifact_has_no_admission_or_commit_channel():
    # Public surface must not imply that a necessary fact is sufficient to
    # admit a call, or install itself as a side effect of import.
    import aos_api.aip_shared_parent_atomic_admission as module
    assert not any(hasattr(module, name) for name in ('admit', 'dispatch', 'commit', 'install'))


def test_new_admission_consumes_both_original_certificate_checks(monkeypatch):
    from aos_api import aip_shared_parent_atomic_admission as admission
    from aos_api import aip_shared_parent_certificate_prepare as original
    calls = []
    def native():
        calls.append('native')
        return 'test-native-requirement'
    def claim():
        calls.append('claim')
        return 'test-original-claim'
    monkeypatch.setattr(original, 'shared_parent_native_verifier_requirement_sql', native)
    monkeypatch.setattr(original, 'shared_parent_certificate_claim_sql', claim)
    assert admission.shared_parent_admission_certificate_validation_sql() == 'test-native-requirementtest-original-claim'
    assert calls == ['native', 'claim']


def test_new_admission_reuses_original_complete_description_kernel(monkeypatch):
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api import aip_physical_capacity_occupation_authority as original
    marker = "-- original complete manifest kernel, not executed"
    monkeypatch.setattr(original, "shared_parent_description_validation_sql", lambda: marker)
    assert api.shared_parent_admission_description_validation_sql() == marker


def test_native_versioned_origin_definition_privilege_and_rollback(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    assert native.execute('SELECT to_regprocedure(%s)', (api.ORIGIN,)).fetchone()[0] is None
    for statement in api.shared_parent_admission_origin_statements():
        native.execute(statement)
    row = native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.ORIGIN,)).fetchone()
    assert row == (OWNER, True, ['search_path=pg_catalog'])
    assert not native.execute('SELECT has_function_privilege(%s,%s,%s)', ('aos_runtime',api.ORIGIN,'EXECUTE')).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_ORIGINAL_FACT_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.build_shared_parent_admission_origin(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)', (api.ORIGIN,)).fetchone()[0] is None


def test_versioned_origin_reuses_original_complete_risk_and_manifest_kernels(monkeypatch):
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api import aip_physical_capacity_occupation_authority as original
    monkeypatch.setattr(original,'shared_parent_original_risk_body_sql',lambda:'--risk kernel marker')
    monkeypatch.setattr(original,'shared_parent_description_validation_sql',lambda:'--manifest kernel marker')
    producer=api.shared_parent_admission_origin_statements()[0]
    assert '--risk kernel marker' in producer and '--manifest kernel marker' in producer
    assert 'INSERT INTO' not in producer and 'UPDATE ' not in producer and 'COMMIT' not in producer
    assert 'FROM aos_physical_capacity_occupation_private.prepared_' not in producer


def test_native_closed_issuer_delegate_metadata_and_admin_rejection(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api.aip_shared_parent_certificate_prepare import ISSUER_OWNER
    for statement in api.shared_parent_admission_origin_statements():
        native.execute(statement)
    for statement in api.shared_parent_admission_certificate_set_statements():
        native.execute(statement)
    row = native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.CERTIFICATE_SET,)).fetchone()
    assert row == (ISSUER_OWNER, True, ['search_path=pg_catalog'])
    for role in ('aos_runtime', 'aos_provider_capacity_issuer', OWNER):
        assert not native.execute('SELECT has_function_privilege(%s,%s,%s)', (role,api.CERTIFICATE_SET,'EXECUTE')).fetchone()[0]
    assert native.execute('SELECT has_function_privilege(%s,%s,%s)', (ISSUER_OWNER,api.ORIGIN,'EXECUTE')).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_CERTIFICATE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.validate_shared_parent_admission_certificate_set(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)', (api.CERTIFICATE_SET,)).fetchone()[0] is None
    native.rollback()


def test_native_pending_origin_storage_is_closed_and_transaction_bound(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api.aip_shared_parent_certificate_prepare import ISSUER_OWNER
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements()):
        native.execute(statement)
    table = api.ADMISSION_SCHEMA + '.pending_origin'
    row = native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass', (table,)).fetchone()
    assert row == (ISSUER_OWNER, True, True)
    for role in ('aos_runtime', 'aos_provider_capacity_issuer', OWNER):
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
            assert not native.execute('SELECT has_table_privilege(%s,%s,%s)', (role,table,privilege)).fetchone()[0]
    guard = native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_admission_end'", (table,)).fetchone()
    assert guard == (True, True)
    assert native.execute('SELECT to_regprocedure(%s)', (api.END_CHANNEL,)).fetchone()[0] is None
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_CERTIFICATE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.persist_shared_parent_admission_origin(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regclass(%s)', (table,)).fetchone()[0] is None
    native.rollback()


def test_native_pending_origin_lookup_delegates_only_fixed_function(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api.aip_shared_parent_certificate_prepare import ISSUER_OWNER
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements(),
                      *api.shared_parent_pending_origin_lookup_statements()):
        native.execute(statement)
    row = native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.READ_PENDING,)).fetchone()
    assert row == (ISSUER_OWNER, True, ['search_path=pg_catalog'])
    assert native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (OWNER,api.READ_PENDING)).fetchone()[0]
    for role in ('aos_runtime','aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role,api.READ_PENDING)).fetchone()[0]
    assert not native.execute("SELECT has_schema_privilege(%s,%s,'USAGE')", (OWNER,api.ADMISSION_SCHEMA)).fetchone()[0]
    assert not native.execute("SELECT has_table_privilege(%s,%s,'SELECT')", (OWNER,api.ADMISSION_SCHEMA+'.pending_origin')).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_CERTIFICATE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.read_shared_parent_pending_origin(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)', (api.READ_PENDING,)).fetchone()[0] is None
    native.rollback()


def test_native_first_target_obligation_is_closed_and_pending(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements(),
                      *api.shared_parent_pending_origin_lookup_statements(),
                      *api.shared_parent_physical_obligation_statements()):
        native.execute(statement)
    table=api.PHYSICAL_SCHEMA+'.initial_target_obligation'
    assert native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(OWNER,True,True)
    for role in ('aos_runtime','aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,api.INITIAL_OBLIGATION)).fetchone()[0]
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
            assert not native.execute('SELECT has_table_privilege(%s,%s,%s)',(role,table,privilege)).fetchone()[0]
    assert native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_obligation_end'",(table,)).fetchone()==(True,True)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with native.transaction():native.execute('SELECT public.prepare_shared_parent_initial_target_obligation(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regclass(%s)',(table,)).fetchone()[0] is None
    native.rollback()


def test_original_capacity_generators_remain_byte_exact():
    from aos_api import aip_physical_capacity_occupation_authority as original
    root=Path(__file__).resolve().parents[4]
    before=json.loads((root/'.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/capacity-kernel-sql-beforeimage-1699.json').read_text())['generators']
    for name,statements in before.items():
        assert list(getattr(original,name)())==statements,name


def test_native_shared_intent_dependency_is_closed(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements(),
                      *api.shared_parent_pending_origin_lookup_statements(),
                      *api.shared_parent_physical_obligation_statements(),
                      *api.shared_parent_initial_intent_statements()):
        native.execute(statement)
    for name in ('target_intent','judge_dependency'):
        table=api.PHYSICAL_SCHEMA+'.'+name
        assert native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(OWNER,True,True)
        for role in ('aos_runtime','aos_provider_capacity_issuer'):
            for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
                assert not native.execute('SELECT has_table_privilege(%s,%s,%s)',(role,table,privilege)).fetchone()[0]
        assert native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_intent_end'",(table,)).fetchone()==(True,True)
    for role in ('aos_runtime','aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,api.INITIAL_INTENT)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SHARED_ADMISSION_INTENT_NATIVE_CALLER_REQUIRED'):
        with native.transaction():native.execute('SELECT public.prepare_shared_parent_initial_intents(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)',(api.INITIAL_INTENT,)).fetchone()[0] is None
    native.rollback()


def test_native_retained_end_authority_is_closed_and_caller_bound(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    from aos_api.aip_shared_parent_certificate_prepare import ISSUER_OWNER
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements(),
                      *api.shared_parent_pending_origin_lookup_statements(),
                      *api.shared_parent_end_authority_statements()):
        native.execute(statement)
    table = api.ADMISSION_SCHEMA + '.end_authority'
    assert native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass', (table,)).fetchone() == (ISSUER_OWNER, True, True)
    for role in ('aos_runtime', 'aos_provider_capacity_issuer', OWNER):
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
            assert not native.execute('SELECT has_table_privilege(%s,%s,%s)', (role,table,privilege)).fetchone()[0]
    for signature in (api.STAGE_AUTHORITY, api.READ_RETAINED):
        assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (signature,)).fetchone() == (ISSUER_OWNER, True, ['search_path=pg_catalog'])
        for role in ('aos_runtime', 'aos_provider_capacity_issuer'):
            assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role,signature)).fetchone()[0]
    assert native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (OWNER,api.READ_RETAINED)).fetchone()[0]
    assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (OWNER,api.STAGE_AUTHORITY)).fetchone()[0]
    assert not native.execute("SELECT has_schema_privilege(%s,%s,'USAGE')", (OWNER,api.ADMISSION_SCHEMA)).fetchone()[0]
    assert native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_authority_end'", (table,)).fetchone() == (True, True)
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_RETAINED_NATIVE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.read_shared_parent_retained_origin(NULL,NULL,NULL,NULL)')
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_AUTHORITY_NATIVE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.stage_shared_parent_end_authority('+','.join(['NULL']*13)+')')
    native.rollback()
    assert native.execute('SELECT to_regclass(%s)', (table,)).fetchone()[0] is None
    native.rollback()


def test_native_initial_call_authority_is_closed_and_caller_bound(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements(),
                      *api.shared_parent_pending_origin_lookup_statements(),
                      *api.shared_parent_physical_obligation_statements(),
                      *api.shared_parent_initial_intent_statements(),
                      *api.shared_parent_end_authority_statements(),
                      *api.shared_parent_initial_call_authority_statements()):
        native.execute(statement)
    table=api.PHYSICAL_SCHEMA+'.initial_call_authority'
    assert native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(OWNER,True,True)
    for signature in (api.STAGE_INITIAL_CALL,api.READ_INITIAL_CALL):
        assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',(signature,)).fetchone()==(OWNER,True,['search_path=pg_catalog'])
        for role in ('aos_runtime','aos_provider_capacity_issuer'):
            assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,signature)).fetchone()[0]
    for role in ('aos_runtime','aos_provider_capacity_issuer'):
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
            assert not native.execute('SELECT has_table_privilege(%s,%s,%s)',(role,table,privilege)).fetchone()[0]
    assert native.execute("SELECT count(*) FROM pg_constraint WHERE conrelid=%s::regclass AND contype='f'",(table,)).fetchone()[0]==3
    assert native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_call_end'",(table,)).fetchone()==(True,True)
    for name,count in [('stage_shared_parent_initial_call_authority',18),('read_shared_parent_initial_call_authority',4)]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SHARED_ADMISSION_CALL_NATIVE_CALLER_REQUIRED'):
            with native.transaction():native.execute('SELECT public.'+name+'('+','.join(['NULL']*count)+')')
    native.rollback()
    assert native.execute('SELECT to_regclass(%s)',(table,)).fetchone()[0] is None
    native.rollback()


def test_native_initial_window_obligation_closed_metadata(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for statement in (*api.shared_parent_admission_origin_statements(),
                      *api.shared_parent_admission_certificate_set_statements(),
                      *api.shared_parent_admission_storage_statements(),
                      *api.shared_parent_pending_origin_lookup_statements(),
                      *api.shared_parent_physical_obligation_statements(),
                      *api.shared_parent_initial_intent_statements(),
                      *api.shared_parent_end_authority_statements(),
                      *api.shared_parent_initial_call_authority_statements(),
                      *api.shared_parent_initial_window_obligation_statements()):
        native.execute(statement)
    table=api.PHYSICAL_SCHEMA+'.initial_window_obligation'
    assert native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(OWNER,True,True)
    assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',(api.STAGE_INITIAL_WINDOW,)).fetchone()==(OWNER,True,['search_path=pg_catalog'])
    for role in ('aos_runtime','aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,api.STAGE_INITIAL_WINDOW)).fetchone()[0]
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
            assert not native.execute('SELECT has_table_privilege(%s,%s,%s)',(role,table,privilege)).fetchone()[0]
    assert native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_window_end'",(table,)).fetchone()==(True,True)
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SHARED_ADMISSION_WINDOW_NATIVE_CALLER_REQUIRED'):
        with native.transaction():native.execute('SELECT public.stage_shared_parent_initial_window_obligation(NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regclass(%s)',(table,)).fetchone()[0] is None
    native.rollback()


def test_native_live_physical_facts_closed_metadata(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for generator in (api.shared_parent_admission_origin_statements,
                      api.shared_parent_admission_certificate_set_statements,
                      api.shared_parent_admission_storage_statements,
                      api.shared_parent_pending_origin_lookup_statements,
                      api.shared_parent_physical_obligation_statements,
                      api.shared_parent_initial_intent_statements,
                      api.shared_parent_end_authority_statements,
                      api.shared_parent_initial_call_authority_statements,
                      api.shared_parent_initial_window_obligation_statements,
                      api.shared_parent_live_physical_fact_statements):
        for statement in generator():native.execute(statement)
    sig=api.READ_LIVE_PHYSICAL
    assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',(sig,)).fetchone()==(OWNER,True,['search_path=pg_catalog'])
    for role in ('aos_runtime','aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,sig)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SHARED_ADMISSION_LIVE_PHYSICAL_CALLER_REQUIRED'):
        with native.transaction():native.execute('SELECT public.read_shared_parent_live_physical_facts(NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)',(sig,)).fetchone()[0] is None
    native.rollback()


def test_native_complete_parent_risk_closed_metadata(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for generator in (api.shared_parent_admission_origin_statements,
                      api.shared_parent_admission_certificate_set_statements,
                      api.shared_parent_admission_storage_statements,
                      api.shared_parent_pending_origin_lookup_statements,
                      api.shared_parent_physical_obligation_statements,
                      api.shared_parent_end_authority_statements,
                      api.shared_parent_complete_parent_risk_statements):
        for statement in generator():
            native.execute(statement)
    sig = api.STAGE_PARENT_RISK
    table = api.PHYSICAL_SCHEMA + '.complete_parent_risk'
    assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (sig,)).fetchone() == (OWNER, True, ['search_path=pg_catalog'])
    assert native.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass', (table,)).fetchone() == (True, True)
    constraints = native.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s::regclass AND contype='u'", (table,)).fetchall()
    assert ('UNIQUE (org_id, project_id, target_request, judge_request)',) in constraints
    trigger = native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_risk_end'", (table,)).fetchone()
    assert trigger == (True, True)
    for role in ('aos_runtime', 'aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, sig)).fetchone()[0]
        assert not native.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')", (role, table)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_RISK_NATIVE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.stage_shared_parent_complete_risk(NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)', (sig,)).fetchone()[0] is None
    assert native.execute('SELECT to_regclass(%s)', (table,)).fetchone()[0] is None
    native.rollback()


def test_final_call_comparison_exact_composition_and_original_generators():
    from aos_api import aip_shared_parent_atomic_admission as api
    statements = api.shared_parent_final_call_validation_statements()
    original = next(s for s in api.shared_parent_initial_call_authority_statements()
                    if s.startswith('CREATE FUNCTION ' + api.READ_INITIAL_CALL.split('(')[0] + '('))
    expected = original.replace('CREATE FUNCTION ' + api.READ_INITIAL_CALL.split('(')[0] + '(',
                                'CREATE FUNCTION ' + api.FINAL_CALL.split('(')[0] + '(', 1)
    expected = expected.replace('verified:=' + api.INITIAL_INTENT.split('(')[0] + '(',
                                'verified:=' + api.FINAL_INTENT.split('(')[0] + '(', 1)
    assert statements[0] == expected
    assert api.INITIAL_INTENT.split('(')[0] not in statements[0]
    assert api._initial_call_material_binding_sql() in statements[0]
    assert api._retained_source_packet_validation_sql() in statements[0]
    assert api.READ_RETAINED.split('(')[0] in statements[0]
    assert not re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b', statements[0], re.I)
    root = Path(__file__).resolve().parents[4]
    frozen = json.loads((root / '.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/final-call-comparison-1755/beforeimage.json').read_text())
    for name, digest in frozen.items():
        assert hashlib.sha256('\n'.join(getattr(api, name)()).encode()).hexdigest() == digest, name


@pytest.mark.parametrize('drift', ['missing', 'duplicate_call', 'missing_call', 'writer'])
def test_final_call_comparison_rejects_reader_drift(monkeypatch, drift):
    from aos_api import aip_shared_parent_atomic_admission as api
    original = api.shared_parent_initial_call_authority_statements
    prefix = 'CREATE FUNCTION ' + api.READ_INITIAL_CALL.split('(')[0] + '('
    call = 'verified:=' + api.INITIAL_INTENT.split('(')[0] + '('
    def changed():
        values = list(original())
        for i, sql in enumerate(values):
            if sql.startswith(prefix):
                if drift == 'missing': values.pop(i)
                elif drift == 'duplicate_call': values[i] = sql.replace(call, call + call, 1)
                elif drift == 'missing_call': values[i] = sql.replace(call, 'verified:=wrong(', 1)
                else: values[i] = sql.replace('RETURN verified', 'DELETE FROM extra_table; RETURN verified', 1)
                break
        return tuple(values)
    monkeypatch.setattr(api, 'shared_parent_initial_call_authority_statements', changed)
    with pytest.raises(ValueError, match='SHARED_ADMISSION_FINAL_CALL_'):
        api.shared_parent_final_call_validation_statements()


def test_native_final_call_comparison_closed_and_rollback(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for generator in (api.shared_parent_admission_origin_statements,
                      api.shared_parent_admission_certificate_set_statements,
                      api.shared_parent_admission_storage_statements,
                      api.shared_parent_pending_origin_lookup_statements,
                      api.shared_parent_physical_obligation_statements,
                      api.shared_parent_initial_intent_statements,
                      api.shared_parent_end_authority_statements,
                      api.shared_parent_initial_call_authority_statements,
                      api.shared_parent_final_intent_validation_statements,
                      api.shared_parent_final_call_validation_statements):
        for sql in generator(): native.execute(sql)
    expected_body = re.search(r'\$call_read\$(.*?)\$call_read\$', api.shared_parent_final_call_validation_statements()[0], re.S)[1]
    assert native.execute('SELECT prosrc,pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.FINAL_CALL,)).fetchone() == (expected_body, OWNER, True, ['search_path=pg_catalog'])
    assert not native.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE')", (api.FINAL_CALL,)).fetchone()[0]
    for role in ('aos_runtime', 'aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, api.FINAL_CALL)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_CALL_NATIVE_CALLER_REQUIRED'):
        with native.transaction():
            native.execute('SELECT public.verify_shared_parent_final_call_authority(NULL,NULL,NULL,NULL)')
    native.rollback()
    assert native.execute('SELECT to_regprocedure(%s)', (api.FINAL_CALL,)).fetchone()[0] is None
    native.rollback()


def test_complete_receipt_fixed_nodes_and_original_generators():
    from aos_api import aip_shared_parent_atomic_admission as api
    statements = api.shared_parent_complete_receipt_statements()
    sql = '\n'.join(statements)
    for name in ('pendingOrigin', 'endAuthority', 'initialTargetObligation', 'targetIntent',
                 'judgeDependency', 'initialCallAuthority', 'initialWindowObligation', 'completeParentRisk'):
        assert "'" + name + "'" in sql
    for callee in (api.READ_RECEIPT_ORIGIN, api.FINAL_CALL, api.READ_LIVE_PHYSICAL):
        assert callee.split('(')[0] in sql
    assert 'window_row.body->>\'accountVersion\'' not in sql
    assert 'awaiting_complete_native_end' in sql
    assert 'windowExpiryReleasesRisk' in sql and 'unknownCommitRetainsRisk' in sql
    stage = next(x for x in statements if x.startswith('CREATE FUNCTION ' + api.STAGE_COMPLETE_RECEIPT.split('(')[0]))
    assert stage.index('INSERT INTO') < stage.index(api.READ_RECEIPT_ORIGIN.split('(')[0] + '(')
    assert 'SHARED_ADMISSION_RECEIPT_ALREADY_STAGED' in stage
    assert 'p_body' not in stage and 'p_facts' not in stage
    root = Path(__file__).resolve().parents[4]
    frozen = json.loads((root / '.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/complete-receipt-1757/beforeimage.json').read_text())
    for name, digest in frozen.items():
        assert hashlib.sha256('\n'.join(getattr(api, name)()).encode()).hexdigest() == digest, name


def test_native_complete_receipt_closed_metadata_and_rollback(native):
    from aos_api import aip_shared_parent_atomic_admission as api
    for generator in (api.shared_parent_admission_origin_statements, api.shared_parent_admission_certificate_set_statements,
                      api.shared_parent_admission_storage_statements, api.shared_parent_pending_origin_lookup_statements,
                      api.shared_parent_physical_obligation_statements, api.shared_parent_initial_intent_statements,
                      api.shared_parent_end_authority_statements, api.shared_parent_initial_call_authority_statements,
                      api.shared_parent_initial_window_obligation_statements, api.shared_parent_live_physical_fact_statements,
                      api.shared_parent_complete_parent_risk_statements, api.shared_parent_final_intent_validation_statements,
                      api.shared_parent_final_call_validation_statements, api.shared_parent_complete_receipt_statements):
        for statement in generator(): native.execute(statement)
    table = api.PHYSICAL_SCHEMA + '.complete_receipt'
    assert native.execute('SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass', (table,)).fetchone() == (OWNER, True, True)
    assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.STAGE_COMPLETE_RECEIPT,)).fetchone() == (OWNER, True, ['search_path=pg_catalog'])
    assert native.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure', (api.READ_RECEIPT_ORIGIN,)).fetchone() == (api._certificate.ISSUER_OWNER, True, ['search_path=pg_catalog'])
    assert native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (OWNER, api.READ_RECEIPT_ORIGIN)).fetchone()[0]
    for role in ('aos_runtime', 'aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, api.READ_RECEIPT_ORIGIN)).fetchone()[0]
    for role in ('aos_runtime', 'aos_provider_capacity_issuer'):
        assert not native.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", (role, api.STAGE_COMPLETE_RECEIPT)).fetchone()[0]
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
            assert not native.execute('SELECT has_table_privilege(%s,%s,%s)', (role, table, privilege)).fetchone()[0]
    assert native.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_receipt_end'", (table,)).fetchone() == (True, True)
    assert native.execute("SELECT count(*) FROM pg_constraint WHERE conrelid=%s::regclass AND contype='f'", (table,)).fetchone()[0] == 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_RECEIPT_NATIVE_CALLER_REQUIRED'):
        with native.transaction(): native.execute('SELECT public.stage_shared_parent_complete_receipt(NULL,NULL,NULL,NULL)')
    # Test-owned identity impersonation checks only early context/missing nodes,
    # not an authenticated supplier Source positive. All grants roll back.
    assert not native.execute("SELECT pg_has_role('aos_provider_capacity_occupation','aos_runtime','MEMBER')").fetchone()[0]
    wrapper = 'public.test_owned_complete_receipt_probe()'
    native.execute("CREATE FUNCTION " + wrapper + " RETURNS jsonb LANGUAGE SQL SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT public.stage_shared_parent_complete_receipt('11111111-1111-1111-1111-111111111111'::uuid,'sha256:'||repeat('0',64),pg_current_xact_id(),pg_backend_pid()) $$")
    native.execute('ALTER FUNCTION ' + wrapper + ' OWNER TO ' + OWNER)
    native.execute('REVOKE ALL ON FUNCTION ' + wrapper + ' FROM PUBLIC')
    native.execute('GRANT EXECUTE ON FUNCTION ' + wrapper + ' TO aos_runtime')
    native.execute('GRANT aos_runtime TO aos_provider_capacity_occupation')
    native.execute('SET SESSION AUTHORIZATION aos_provider_capacity_occupation')
    native.execute('SET LOCAL ROLE aos_runtime')
    native.execute("SET LOCAL TimeZone='UTC'")
    native.execute("SET LOCAL aos.project_id='dev-project'")
    native.execute("SET LOCAL aos.org_id='dev-org'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_RECEIPT_NATIVE_CALLER_REQUIRED'):
        with native.transaction(): native.execute('SELECT ' + wrapper)
    native.execute("SET LOCAL aos.org_id='org-org'")
    with pytest.raises(psycopg.errors.CheckViolation, match='SHARED_ADMISSION_RECEIPT_COMPLETE_NODES_REQUIRED'):
        with native.transaction(): native.execute('SELECT ' + wrapper)
    native.execute('RESET ROLE')
    native.execute('RESET SESSION AUTHORIZATION')
    assert native.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
    native.rollback()
    assert native.execute('SELECT to_regclass(%s)', (table,)).fetchone()[0] is None
    native.rollback()


@pytest.mark.parametrize('drift', ['missing', 'return_boundary', 'writer'])
def test_receipt_origin_delegate_rejects_original_drift(monkeypatch, drift):
    from aos_api import aip_shared_parent_atomic_admission as api
    original = api.shared_parent_end_authority_statements
    prefix = 'CREATE FUNCTION ' + api.READ_RETAINED.split('(')[0] + '('
    def changed():
        values = list(original())
        for i, sql in enumerate(values):
            if sql.startswith(prefix):
                if drift == 'missing': values.pop(i)
                elif drift == 'return_boundary': values[i] = sql.replace('RETURN verified||', 'RETURN changed||', 1)
                else: values[i] = sql.replace('RETURN verified||', 'DELETE FROM extra_table; RETURN verified||', 1)
                break
        return tuple(values)
    monkeypatch.setattr(api, 'shared_parent_end_authority_statements', changed)
    with pytest.raises(ValueError, match='SHARED_ADMISSION_RECEIPT_ORIGIN_'):
        api.shared_parent_receipt_origin_statements()
