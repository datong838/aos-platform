"""Dedicated protected UI API identity; never reuse runtime or general Web DSNs."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

from aos_api.tenant_scope import TenantScope
from .ui_current_principal import _exact

CREDENTIAL_FILE = 'AOS_RUNTIME_UI_READ_CREDENTIAL_FILE'


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate identity field')
        value[key] = item
    return value


def _identity():
    try:
        reference = os.getenv(CREDENTIAL_FILE, '').strip()
        path = Path(reference)
        if not reference or not path.is_absolute():
            raise ValueError()
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'r', encoding='utf-8') as handle:
            metadata = os.fstat(handle.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_uid != os.getuid() or not 0 < metadata.st_size <= 65536):
                raise ValueError()
            value = json.loads(handle.read(65537), object_pairs_hook=_unique)
        if (type(value) is not dict or set(value) != {'schemaVersion', 'dsn', 'role'}
                or value['schemaVersion'] != 'aos.runtime-ui-api-identity/v1'
                or type(value['role']) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}', value['role']) is None
                or value['role'] == 'aos_ui_read_api' or not _exact(value['dsn']) or len(value['dsn']) > 65536):
            raise ValueError()
        return value
    except Exception:
        raise RuntimeError('UI read identity reference is invalid') from None


def _verify(conn, expected_role):
    row = conn.execute('''SELECT session_user AS session_name,current_user AS current_name,
        rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit
        FROM pg_catalog.pg_roles WHERE rolname=session_user''').fetchone()
    denied = ('rolsuper', 'rolbypassrls', 'rolcreaterole', 'rolcreatedb', 'rolreplication')
    if (row is None or row['session_name'] != expected_role or row['current_name'] != expected_role
            or row['rolcanlogin'] is not True or row['rolinherit'] is not False
            or any(row[key] is not False for key in denied)):
        raise RuntimeError('UI read identity is not permitted')
    roles = conn.execute('''SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication FROM pg_catalog.pg_roles
        WHERE rolname<>session_user AND pg_has_role(session_user,oid,'MEMBER')''').fetchall()
    unsafe = conn.execute('''SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid=m.member
        WHERE (r.rolname=session_user AND m.admin_option) OR r.rolname='aos_ui_read_api') AS unsafe''').fetchone()
    if ([r['rolname'] for r in roles] != ['aos_ui_read_api'] or unsafe['unsafe'] is not False
            or any(r[key] is not False for r in roles for key in ('rolcanlogin', *denied))):
        raise RuntimeError('UI read identity is not permitted')


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
