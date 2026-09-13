import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest

from test_ui_read_consumer_pg import (consumer_case, host_snapshot, projector, host_role,
    api_role, admission, queue, attempt_case, database, snapshot, SCOPE, prepare, pytestmark)
from test_ui_read_api_role_pg import caller
from test_ui_read_admission_pg import SchemaConnection
from aos_api.extension_runtime.ui_read_query import RuntimeUiReadQuery
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.fixture
def query_case(consumer_case, host_role):
    owner, _, schema, _ = host_role
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_035_runtime_ui_read_query.py'
    spec = importlib.util.spec_from_file_location('ui_query_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=lambda q: owner.execute(
        q.replace('public.', schema + '.').replace('pg_catalog,public,pg_temp', f'pg_catalog,{schema},pg_temp')))
    migration.upgrade()
    return consumer_case, host_role, RuntimeUiReadQuery(catalog=consumer_case[0].catalog)


def query(case, *, subject='reader', org='org-org', request_id=None):
    consumer, role, service = case
    request_id = request_id or UUID(consumer[-1]['requestId'])
    with caller(role, subject=subject, org=org) as conn:
        return service.get(conn=SchemaConnection(conn, role[2]), scope=type(SCOPE)(org, SCOPE.project_id),
                           subject=subject, required_markings=('public',), request_id=request_id)


def test_original_subject_reads_pending_and_success_with_no_new_attempt(query_case):
    case, role, _ = query_case
    pending = query(query_case)
    assert pending['state'] == 'requested' and pending['result'] is None
    prepared = prepare(case)
    outcome = asyncio.run(case[0].invoke_prepared(prepared))
    case[0].finish_prepared(prepared, outcome)
    result = query(query_case)
    assert result['state'] == 'succeeded' and result['result']['caseCount'] == 1
    assert query(query_case) == result
    assert role[0].execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone() == (1,)


@pytest.mark.parametrize('failure', ['other', 'canary', 'missing', 'revoked', 'resource', 'binding'])
def test_queries_reject_stale_or_foreign_authority(query_case, failure):
    case, role, _ = query_case
    owner = role[0]
    kwargs = {}
    error = RuntimeConflict
    if failure in ('other', 'canary'):
        subject, org = ('query-other', 'org-org') if failure == 'other' else ('reader', 'dev-org')
        owner.execute('INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s)',
                      (org, 'dev-project', subject, 'reader'))
        owner.execute('INSERT INTO authz_tuple VALUES(%s,%s,%s,%s,%s)',
                      (org, 'dev-project', 'user:' + subject, 'bearer', 'marking:public'))
        kwargs = dict(subject=subject, org=org)
        error = LookupError
    if failure == 'missing':
        kwargs['request_id'] = uuid4()
        error = LookupError
    if failure == 'revoked':
        owner.execute("DELETE FROM meta_membership WHERE subject='reader'")
    if failure == 'resource':
        case[2].ui.resourceHash = 'sha256:' + 'b' * 64
    if failure == 'binding':
        owner.execute('UPDATE extension_runtime_binding SET revision=revision+1')
    with pytest.raises(error):
        query(query_case, **kwargs)


def test_metadata_excludes_result_and_api_cannot_select_table(query_case):
    case, role, _ = query_case
    with caller(role) as conn:
        value = conn.execute('SELECT extension_ui_read_metadata_a0v_035(%s,%s)',
                             ('reader', UUID(case[-1]['requestId']))).fetchone()[0]
        assert set(value) == {'requestId', 'requestHash', 'request'}
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT result_json FROM extension_runtime_ui_read_request')


def test_catalog_rejection_precedes_result_function(query_case, monkeypatch):
    case, role, service = query_case
    case[2].ui.readOperationClaims = ()
    calls = []
    execute = SchemaConnection.execute
    def observe(self, query, params=None):
        if 'extension_ui_read_result_a0v_035' in query:
            calls.append(query)
        return execute(self, query, params)
    monkeypatch.setattr(SchemaConnection, 'execute', observe)
    with pytest.raises(RuntimeConflict):
        query(query_case)
    assert calls == []


def test_failed_read_has_only_fixed_failure_no_business_result(query_case):
    case, _, _ = query_case
    case[4]['result'] = 'unknown'
    prepared = prepare(case)
    outcome = asyncio.run(case[0].invoke_prepared(prepared))
    case[0].finish_prepared(prepared, outcome)
    value = query(query_case)
    assert value['state'] == 'failed'
    assert value['failureCode'] == 'READ_OUTCOME_UNKNOWN'
    assert value['result'] is None and value['resultHash'] is None


def test_exact_request_digest_is_required_by_database(query_case):
    case, role, _ = query_case
    with caller(role) as conn:
        assert conn.execute('SELECT extension_ui_read_result_a0v_035(%s,%s,%s)',
            ('reader', UUID(case[-1]['requestId']), 'sha256:' + '0' * 64)).fetchone() == (None,)


@pytest.mark.parametrize('kind', ['superuser', 'repeatable'])
def test_query_functions_retain_session_identity_boundary(query_case, kind):
    case, role, _ = query_case
    with caller(role, privileged=kind == 'superuser', repeatable=kind == 'repeatable') as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT extension_ui_read_metadata_a0v_035(%s,%s)',
                         ('reader', UUID(case[-1]['requestId'])))
