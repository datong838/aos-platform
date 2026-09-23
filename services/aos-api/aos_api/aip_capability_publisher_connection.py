"""Explicit protected identity for the AIP capability publisher; no runtime fallback."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

_CREDENTIAL_FILE = 'AOS_AIP_CAPABILITY_PUBLISHER_CREDENTIAL_FILE'
_SCHEMA = 'aos.aip.capability-publisher-identity/v1'
_ROLES = frozenset(('aos_aip_capability_publisher',))


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate identity field')
        result[key] = value
    return result


def _identity_file():
    try:
        reference = os.getenv(_CREDENTIAL_FILE, '').strip()
        path = Path(reference)
        if not reference or not path.is_absolute():
            raise ValueError('absolute reference required')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'r', encoding='utf-8') as handle:
            metadata = os.fstat(handle.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_uid != os.getuid() or not 0 < metadata.st_size <= 65536):
                raise ValueError('protected file required')
            raw = handle.read(65537)
        if len(raw.encode('utf-8')) > 65536:
            raise ValueError('identity too large')
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
        if (type(value) is not dict or set(value) != {'schemaVersion', 'dsn', 'role'}
                or value['schemaVersion'] != _SCHEMA
                or type(value['role']) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}', value['role']) is None
                or value['role'] in _ROLES
                or type(value['dsn']) is not str or not value['dsn']
                or value['dsn'] != value['dsn'].strip() or '\x00' in value['dsn']):
            raise ValueError('identity shape differs')
        return value
    except Exception:
        raise RuntimeError('capability publisher identity reference is invalid') from None


def _verify_identity(conn, role):
    row = conn.execute('''SELECT session_user AS session_name,current_user AS current_name,
        rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit
        FROM pg_catalog.pg_roles WHERE rolname=session_user''').fetchone()
    denied = ('rolsuper', 'rolbypassrls', 'rolcreaterole', 'rolcreatedb', 'rolreplication')
    if (row is None or row['session_name'] != role or row['current_name'] != role
            or row['rolcanlogin'] is not True or row['rolinherit'] is not False
            or any(row[key] is not False for key in denied)):
        raise ValueError('independent unprivileged login required')
    reachable = conn.execute('''SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
        FROM pg_catalog.pg_roles WHERE rolname<>session_user
        AND pg_catalog.pg_has_role(session_user,oid,'MEMBER')''').fetchall()
    if ({item['rolname'] for item in reachable} != _ROLES or len(reachable) != 1
            or any(item[key] is not False for item in reachable for key in ('rolcanlogin', *denied))):
        raise ValueError('exact unprivileged role set required')
    unsafe = conn.execute('''SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid=m.member
        WHERE (r.rolname=session_user AND m.admin_option)
           OR r.rolname='aos_aip_capability_publisher') AS unsafe''').fetchone()
    if unsafe is None or unsafe['unsafe'] is not False:
        raise ValueError('role administration or inherited control denied')


@contextmanager
def capability_publisher_connection():
    identity = _identity_file()
    try:
        conn = psycopg.connect(identity['dsn'], row_factory=dict_row, connect_timeout=10)
    except Exception:
        raise RuntimeError('capability publisher identity connection unavailable') from None
    with conn:
        try:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('idle connection required')
            with conn.transaction():
                conn.execute("SET LOCAL statement_timeout='3s'")
                _verify_identity(conn, identity['role'])
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('identity check must finish its transaction')
        except Exception:
            raise RuntimeError('capability publisher identity is not permitted') from None
        yield conn


def configured_capability_publisher_connection():
    """Select only the fixed connector; construction reads no secret or database.

    Returns None when the credential file is not configured -- callers must
    treat that as "publisher not wired" and fail loudly, never silently fall
    back to the runtime identity (fail-closed, see B-plan §四).
    """
    return capability_publisher_connection if os.getenv(_CREDENTIAL_FILE, '').strip() else None
