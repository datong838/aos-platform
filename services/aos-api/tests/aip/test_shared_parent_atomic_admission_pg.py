"""New admission fact boundary on retained native lab; no admission success claim."""
import json
import os
import re
import subprocess
from pathlib import Path

import psycopg
import pytest

from aos_api.aip_shared_parent_atomic_admission import FUNCTION, shared_parent_original_fact_statements
from aos_api.aip_physical_capacity_occupation_authority import OWNER, PLAN_FACT, occupation_plan_risk_statements


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
