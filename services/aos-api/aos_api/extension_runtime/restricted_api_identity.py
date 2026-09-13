"""Shared protected identity-file and least-privilege LOGIN checks."""
import json
import os
from pathlib import Path
import re
import stat
from .ui_current_principal import _exact


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate identity field')
        value[key] = item
    return value


def read_identity(reference, *, schema_version, logical_role, label):
    try:
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
                or value['schemaVersion'] != schema_version
                or type(value['role']) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}', value['role']) is None
                or value['role'] == logical_role or not _exact(value['dsn']) or len(value['dsn']) > 65536):
            raise ValueError()
        return value
    except Exception:
        raise RuntimeError(f'{label} identity reference is invalid') from None


def verify_identity(conn, expected_role, *, logical_role, label):
    row = conn.execute('''SELECT session_user AS session_name,current_user AS current_name,
        rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit
        FROM pg_catalog.pg_roles WHERE rolname=session_user''').fetchone()
    denied = ('rolsuper', 'rolbypassrls', 'rolcreaterole', 'rolcreatedb', 'rolreplication')
    if (row is None or row['session_name'] != expected_role or row['current_name'] != expected_role
            or row['rolcanlogin'] is not True or row['rolinherit'] is not False
            or any(row[key] is not False for key in denied)):
        raise RuntimeError(f'{label} identity is not permitted')
    roles = conn.execute('''SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication FROM pg_catalog.pg_roles
        WHERE rolname<>session_user AND pg_has_role(session_user,oid,'MEMBER')''').fetchall()
    unsafe = conn.execute('''SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid=m.member
        WHERE (r.rolname=session_user AND m.admin_option) OR r.rolname=%s) AS unsafe''', (logical_role,)).fetchone()
    if ([r['rolname'] for r in roles] != [logical_role] or unsafe['unsafe'] is not False
            or any(r[key] is not False for r in roles for key in ('rolcanlogin', *denied))):
        raise RuntimeError(f'{label} identity is not permitted')

