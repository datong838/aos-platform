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


@pytest.mark.parametrize('mutation', (None, 'insert', 'delete', 'truncate', 'identity', 'missing_update', 'rls', 'trigger'))
@pytest.mark.parametrize('as_dict', (False, True))
def test_preflight_accepts_only_current_minimal_runtime_rights(stage, database, mutation, as_dict):
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
