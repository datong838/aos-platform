"""Dedicated protected UI API identity; never reuse runtime or general Web DSNs."""
from contextlib import contextmanager
import os

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

from aos_api.tenant_scope import TenantScope
from .ui_current_principal import _exact

CREDENTIAL_FILE = 'AOS_RUNTIME_UI_READ_CREDENTIAL_FILE'


def _identity():
    from .restricted_api_identity import read_identity
    return read_identity(os.getenv(CREDENTIAL_FILE, '').strip(),
        schema_version='aos.runtime-ui-api-identity/v1', logical_role='aos_ui_read_api', label='UI read')


def _verify(conn, expected_role):
    from .restricted_api_identity import verify_identity
    return verify_identity(conn, expected_role, logical_role='aos_ui_read_api', label='UI read')

@contextmanager
def ui_read_connection(*, scope, subject):
    if type(scope) is not TenantScope or not _exact(subject):
        raise ValueError('exact UI request principal required')
    identity = _identity()
    try:
        conn = psycopg.connect(identity['dsn'], row_factory=dict_row, connect_timeout=10)
    except Exception:
        raise RuntimeError('UI read identity connection unavailable') from None
    with conn:
        conn.isolation_level = IsolationLevel.READ_COMMITTED
        with conn.transaction():
            conn.execute("SET LOCAL statement_timeout='10s'")
            conn.execute("SET LOCAL lock_timeout='1s'")
            _verify(conn, identity['role'])
            conn.execute('SET LOCAL ROLE aos_ui_read_api')
            conn.execute('SET LOCAL search_path TO pg_catalog,public')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true),"
                         "set_config('aos.subject',%s,true)", (*scope.key, subject))
            yield conn
