"""Production gate SQL on a disposable schema with a non-owner session identity."""
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_stage_schema_pg import stage, TABLE
from aos_api.extension_runtime.configuration_stage_preflight import configuration_stage_ready


class ScopedSchema:
    def __init__(self, conn, schema): self.conn, self.schema = conn, schema
    @property
    def info(self): return self.conn.info
    def transaction(self): return self.conn.transaction()
    def execute(self, query, params=()):
        return self.conn.execute(query.replace('public.', self.schema+'.'), tuple(
            value.replace('public.', self.schema+'.') if isinstance(value, str) else value for value in params))


@pytest.fixture
def source_acl(stage):
    conn, _, _ = stage
    for table in ('aip_responsibility_plan_head', 'aip_responsibility_plan_revision',
                  'aip_production_contract_receipt'):
        conn.execute(f'CREATE TABLE {table}(id integer)')
        conn.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        conn.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        conn.execute(f'GRANT SELECT ON {table} TO aos_runtime')


@pytest.mark.parametrize('mutation', (None, 'insert', 'delete', 'truncate', 'identity', 'missing_update', 'rls', 'trigger',
                                     'source_head_insert', 'source_revision_update', 'source_receipt_insert',
                                     'source_receipt_delete', 'source_revision_rls'))
@pytest.mark.parametrize('as_dict', (False, True))
def test_preflight_accepts_only_current_minimal_runtime_rights(stage, source_acl, database, mutation, as_dict):
    conn, _, _ = stage
    _, role, schema = database
    changes = {
        'insert': f'GRANT INSERT ON {TABLE} TO aos_runtime',
        'delete': f'GRANT DELETE ON {TABLE} TO aos_runtime',
        'truncate': f'GRANT TRUNCATE ON {TABLE} TO aos_runtime',
        'identity': f'GRANT UPDATE(subject) ON {TABLE} TO aos_runtime',
        'missing_update': f'REVOKE UPDATE(result_json) ON {TABLE} FROM aos_runtime',
        'rls': f'ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY',
        'trigger': f'ALTER TABLE {TABLE} DISABLE TRIGGER configuration_stage_guard',
        'source_head_insert': 'GRANT INSERT ON aip_responsibility_plan_head TO aos_runtime',
        'source_revision_update': 'GRANT UPDATE ON aip_responsibility_plan_revision TO aos_runtime',
        'source_receipt_insert': 'GRANT INSERT ON aip_production_contract_receipt TO aos_runtime',
        'source_receipt_delete': 'GRANT DELETE ON aip_production_contract_receipt TO aos_runtime',
        'source_revision_rls': 'ALTER TABLE aip_responsibility_plan_revision NO FORCE ROW LEVEL SECURITY',
    }
    if mutation: conn.execute(changes[mutation])
    conn.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
    old_factory = conn.row_factory
    try:
        conn.execute('SET ROLE aos_runtime')
        if as_dict: conn.row_factory = dict_row
        assert configuration_stage_ready(ScopedSchema(conn, schema)) is (mutation is None)
    finally:
        conn.row_factory = old_factory
        conn.execute('RESET SESSION AUTHORIZATION')


def test_owner_connection_is_rejected_even_when_schema_is_correct(stage, database):
    conn, _, _ = stage
    assert configuration_stage_ready(ScopedSchema(conn, database[2])) is False


def test_missing_current_source_table_fails_closed(stage, database):
    conn, _, schema = database
    conn.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(database[1])))
    conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(database[1])))
    try:
        conn.execute('SET ROLE aos_runtime')
        assert configuration_stage_ready(ScopedSchema(conn, schema)) is False
    finally:
        conn.execute('RESET SESSION AUTHORIZATION')
