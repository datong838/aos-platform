import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import psycopg

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_stage_schema_pg import stage, TABLE
from test_configuration_stage_api_pg import api, caller, enqueue


@pytest.fixture
def lookup_api(api,database):
    conn=api[0];schema=database[2]
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_038_configuration_stage_lookup.py'
    spec=importlib.util.spec_from_file_location('stage_lookup',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=lambda q:conn.execute(q.replace('public.',schema+'.').replace('pg_catalog,public,pg_temp',f'pg_catalog,{schema},pg_temp')))
    module.upgrade()
    return api


def lookup(conn,key,subject='test-actor'):
    return conn.execute('SELECT extension_configuration_stage_lookup_a0v_038(%s,%s)',(subject,key)).fetchone()[0]


def test_lost_response_is_found_without_resubmission_or_record_growth(lookup_api):
    with caller(lookup_api) as conn: original=enqueue(conn,lookup_api[2],key='lost-response')
    with caller(lookup_api) as conn:
        found=lookup(conn,'lost-response')
        assert found['requestId']==original['requestId']
        assert found['requestHash']==original['requestHash']
        assert lookup(conn,'never-submitted') is None
    with caller(lookup_api,subject='other') as conn: assert lookup(conn,'lost-response',subject='other') is None
    assert lookup_api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==1


def test_lookup_rechecks_revoked_installation_markings(lookup_api):
    with caller(lookup_api) as conn: enqueue(conn,lookup_api[2],key='lost')
    lookup_api[0].execute('DELETE FROM authz_tuple')
    with pytest.raises(psycopg.Error):
        with caller(lookup_api) as conn: lookup(conn,'lost')


@pytest.mark.parametrize('key',('', ' bad ', 'x'*161))
def test_invalid_lookup_key_is_not_a_submission(lookup_api,key):
    with pytest.raises(psycopg.Error):
        with caller(lookup_api) as conn: lookup(conn,key)
    assert lookup_api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==0
