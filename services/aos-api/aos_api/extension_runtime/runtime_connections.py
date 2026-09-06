"""Separate production connections for the cross-tenant directory and tenant workers."""
from contextlib import contextmanager
import os

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus

from aos_api.db import get_dsn


@contextmanager
def runtime_worker_connection():
    """Return an unscoped IDLE connection; the concrete worker owns each transaction."""
    dsn = os.getenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("runtime worker database identity is not configured")
    if dsn == get_dsn():
        raise RuntimeError("runtime worker identity must differ from the web database identity")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        if conn.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("runtime worker connection must start idle")
        yield conn


@contextmanager
def runtime_directory_connection():
    """Use a separately provisioned, host-bound, read-only database identity."""
    dsn = os.getenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("runtime directory database identity is not configured")
    if dsn == get_dsn():
        raise RuntimeError("runtime directory identity must differ from the web database identity")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        if conn.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("runtime directory connection must start idle")
        yield conn
