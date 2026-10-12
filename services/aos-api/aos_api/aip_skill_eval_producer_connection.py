"""Default-off private producer connection; caller explicitly owns commit."""
from contextlib import contextmanager
import os

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_eval_writer_connection import _read_identity_file
from aos_api.aip_skill_eval_producer_identity import require_skill_producer_identity

_CREDENTIAL_FILE = 'AOS_AIP_SKILL_PRODUCER_CREDENTIAL_FILE'


@contextmanager
def skill_producer_connection(*, expected_database: str):
    """Yield an idle verified login, not Owner/budget or execution admission.

    Only an explicit caller commit persists work. Closing an uncommitted
    connection abandons it; no cleanup SQL or operation replay is attempted.
    """
    if not isinstance(expected_database,str) or not expected_database.strip():
        raise RuntimeError('Skill producer expected database is required')
    identity = _read_identity_file(credential_file_env=_CREDENTIAL_FILE,
        schema='aos.aip.skill-producer-identity/v1',role='aos_skill_eval_finisher',
        rejection='Skill producer identity reference is invalid')
    try:
        conn = psycopg.connect(identity['dsn'],row_factory=dict_row,connect_timeout=10)
    except Exception:
        raise RuntimeError('Skill producer identity connection unavailable') from None
    try:
        try:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('idle connection required')
            with conn.transaction():
                conn.execute('SET TRANSACTION READ ONLY')
                conn.execute("SET LOCAL statement_timeout='3s'")
                require_skill_producer_identity(conn,expected_database=expected_database)
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('identity check did not finish')
        except Exception:
            raise RuntimeError('Skill producer identity is not permitted') from None
        yield conn
    finally:
        conn.close()


def configured_skill_producer_connection():
    return skill_producer_connection if os.getenv(_CREDENTIAL_FILE,'').strip() else None
