"""Separate production connections for the cross-tenant directory and tenant workers."""
from contextlib import contextmanager
import os
import json
import stat
from pathlib import Path

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus

from aos_api.db import get_dsn


def _runtime_file_dsns(reference):
    """Read existing host identities in memory; never export secrets to env."""
    try:
        path = Path(reference)
        if not path.is_absolute():
            raise ValueError('absolute credential reference required')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'r', encoding='utf-8') as handle:
            metadata = os.fstat(handle.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_uid != os.getuid() or not 0 < metadata.st_size <= 65536):
                raise ValueError('protected credential file required')
            value = json.loads(handle.read(65537))
        if type(value) is not dict or set(value) != {'web','runtime','directory'}:
            raise ValueError('host identity file shape differs')
        for item in value.values():
            if (type(item) is not dict or set(item) != {'dsn','password','role'}
                    or any(type(v) is not str or not v or '\x00' in v for v in item.values())):
                raise ValueError('host identity entry differs')
        if any(len({item[key] for item in value.values()}) != 3 for key in ('role', 'dsn')):
            raise ValueError('three distinct identities required')
        return {plane: item['dsn'] for plane, item in value.items()}
    except Exception:
        raise RuntimeError('runtime credential reference is invalid') from None


@contextmanager
def runtime_worker_connection():
    """Return an unscoped IDLE connection; the concrete worker owns each transaction."""
    reference = os.getenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "").strip()
    if reference:
        identities = _runtime_file_dsns(reference)
        dsn, web_dsn = identities['runtime'], identities['web']
    else:
        dsn = os.getenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "").strip()
        web_dsn = get_dsn()
    if not dsn:
        raise RuntimeError("runtime worker database identity is not configured")
    if dsn == web_dsn:
        raise RuntimeError("runtime worker identity must differ from the web database identity")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        if conn.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("runtime worker connection must start idle")
        yield conn


@contextmanager
def runtime_directory_connection():
    """Use a separately provisioned, host-bound, read-only database identity."""
    reference = os.getenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "").strip()
    if reference:
        identities = _runtime_file_dsns(reference)
        dsn, web_dsn = identities['directory'], identities['web']
    else:
        dsn = os.getenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "").strip()
        web_dsn = get_dsn()
    if not dsn:
        raise RuntimeError("runtime directory database identity is not configured")
    if dsn == web_dsn:
        raise RuntimeError("runtime directory identity must differ from the web database identity")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        if conn.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("runtime directory connection must start idle")
        yield conn


@contextmanager
def runtime_web_identity_connection():
    """Open the Web principal without request scope solely for identity preflight."""
    reference = os.getenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "").strip()
    dsn = _runtime_file_dsns(reference)['web'] if reference else get_dsn()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        if conn.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("web identity connection must start idle")
        yield conn
