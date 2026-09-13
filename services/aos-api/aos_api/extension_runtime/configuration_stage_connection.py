"""Dedicated configuration API identity; no general Web or Host fallback."""
from contextlib import contextmanager
import os

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope
from .restricted_api_identity import read_identity, verify_identity
from .ui_current_principal import _exact

CREDENTIAL_FILE = 'AOS_RUNTIME_CONFIGURATION_STAGE_CREDENTIAL_FILE'


@contextmanager
def configuration_stage_connection(*, scope, subject):
    if type(scope) is not TenantScope or not _exact(subject):
        raise ValueError('exact configuration request principal required')
    if openfga_api_url():
        raise RuntimeError('remote configuration authority adapter is unavailable')
    identity = read_identity(os.getenv(CREDENTIAL_FILE, '').strip(),
        schema_version='aos.runtime-configuration-api-identity/v1',
        logical_role='aos_configuration_stage_api', label='Configuration staging')
    try:
        conn = psycopg.connect(identity['dsn'], row_factory=dict_row, connect_timeout=10)
    except Exception:
        raise RuntimeError('configuration identity connection unavailable') from None
    with conn:
        conn.isolation_level = IsolationLevel.READ_COMMITTED
        with conn.transaction():
            conn.execute("SET LOCAL statement_timeout='10s'")
            conn.execute("SET LOCAL lock_timeout='1s'")
            verify_identity(conn, identity['role'], logical_role='aos_configuration_stage_api', label='Configuration staging')
            conn.execute('SET LOCAL ROLE aos_configuration_stage_api')
            conn.execute('SET LOCAL search_path TO pg_catalog,public')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true),set_config('aos.subject',%s,true)", (*scope.key, subject))
            yield conn
