"""Native identity boundary; fixture grants confer no real producer authority."""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from aos_api.aip_skill_eval_producer_identity import require_skill_producer_identity


@pytest.fixture
def producer_login():
    name = 'skill_producer_test_' + uuid4().hex[:12]
    parts = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    database = parts['dbname']
    with psycopg.connect(os.environ['AOS_DATABASE_URL'], autocommit=True) as admin:
        new_finisher = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone() is None
        if new_finisher:
            admin.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT')
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT').format(sql.Identifier(name)))
        admin.execute(sql.SQL('GRANT aos_aip_eval_writer,aos_skill_eval_finisher TO {}').format(sql.Identifier(name)))
        admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database), sql.Identifier(name)))
    try:
        yield name, database, make_conninfo(**{**parts, 'user': name})
    finally:
        with psycopg.connect(os.environ['AOS_DATABASE_URL'], autocommit=True) as admin:
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(name)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(name)))
            if new_finisher:
                admin.execute('DROP ROLE aos_skill_eval_finisher')


def test_exact_independent_native_login(producer_login):
    _, database, dsn = producer_login
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        require_skill_producer_identity(conn, expected_database=database)


@pytest.mark.parametrize('drift', ['missing-role', 'extra-role', 'admin-option', 'inherit-login', 'inherited-membership', 'unsettable-membership', 'privileged-login', 'wrong-database', 'switched-role'])
def test_native_identity_drift_refuses(producer_login, drift):
    name, database, dsn = producer_login
    with psycopg.connect(os.environ['AOS_DATABASE_URL'], autocommit=True) as admin:
        if drift == 'missing-role':
            admin.execute(sql.SQL('REVOKE aos_skill_eval_finisher FROM {}').format(sql.Identifier(name)))
        elif drift == 'extra-role':
            admin.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(name)))
        elif drift == 'admin-option':
            admin.execute(sql.SQL('GRANT aos_skill_eval_finisher TO {} WITH ADMIN OPTION').format(sql.Identifier(name)))
        elif drift == 'inherit-login':
            admin.execute(sql.SQL('ALTER ROLE {} INHERIT').format(sql.Identifier(name)))
        elif drift == 'inherited-membership':
            admin.execute(sql.SQL('GRANT aos_skill_eval_finisher TO {} WITH INHERIT TRUE').format(sql.Identifier(name)))
        elif drift == 'unsettable-membership':
            admin.execute(sql.SQL('GRANT aos_skill_eval_finisher TO {} WITH SET FALSE').format(sql.Identifier(name)))
        elif drift == 'privileged-login':
            admin.execute(sql.SQL('ALTER ROLE {} CREATEDB').format(sql.Identifier(name)))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        if drift == 'switched-role':
            conn.execute('SET LOCAL ROLE aos_aip_eval_writer')
        with pytest.raises(RuntimeError, match='independent Skill producer identity'):
            require_skill_producer_identity(conn, expected_database='other' if drift == 'wrong-database' else database)


def test_native_administrator_is_not_producer():
    with psycopg.connect(os.environ['AOS_DATABASE_URL'], row_factory=dict_row) as conn:
        with pytest.raises(RuntimeError, match='independent Skill producer identity'):
            require_skill_producer_identity(conn, expected_database=conn.info.dbname)


def test_original_writer_identity_contract_stays_one_role(producer_login):
    from aos_api.aip_eval_writer_connection import _verify_identity
    name, database, dsn = producer_login
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with pytest.raises(ValueError, match='role reachability'):
            _verify_identity(conn, database)
    with psycopg.connect(os.environ['AOS_DATABASE_URL'], autocommit=True) as admin:
        admin.execute(sql.SQL('REVOKE aos_skill_eval_finisher FROM {}').format(sql.Identifier(name)))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        _verify_identity(conn, database)
        with pytest.raises(RuntimeError, match='independent Skill producer identity'):
            require_skill_producer_identity(conn, expected_database=database)
