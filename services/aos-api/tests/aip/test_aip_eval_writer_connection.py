"""Test-only real PostgreSQL identity gates for the default-off Eval writer."""
from __future__ import annotations

import json
import os
import secrets

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from aos_api.aip_eval_writer_connection import (
    configured_eval_writer_connection, eval_writer_connection,
)

ENV = "AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE"
SCHEMA = "aos.aip.eval-writer-identity/v1"
ROLE = "aos_aip_eval_writer"
LOGIN = "aos_bg00ah_eval_writer_login"


@pytest.fixture()
def test_identity():
    dsn = os.getenv("AOS_BG00AH_TEST_ADMIN_URL")
    if not dsn:
        pytest.skip("isolated BG-00ah PostgreSQL URL required")
    info = conninfo_to_dict(dsn)
    assert info["dbname"] == "aos_bg00ad_schema_v2_20260929"
    assert int(info["port"]) == 5433
    password = secrets.token_urlsafe(32)
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert conn.execute("SELECT current_database()").fetchone()[0] == info["dbname"]
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (ROLE,)).fetchone():
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION").format(sql.Identifier(ROLE)))
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (LOGIN,)).fetchone():
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION").format(sql.Identifier(LOGIN)))
        conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(LOGIN), sql.Literal(password)))
        if not conn.execute("""SELECT 1 FROM pg_auth_members m
            JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles u ON u.oid=m.member
            WHERE r.rolname=%s AND u.rolname=%s""", (ROLE,LOGIN)).fetchone():
            conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(ROLE),sql.Identifier(LOGIN)))
    writer=make_conninfo(dsn,user=LOGIN,password=password)
    return dsn,writer


def _file(tmp_path, dsn, *, schema=SCHEMA, role=ROLE, extra=""):
    path=tmp_path/'eval-writer.json'
    if extra:
        text='{"schemaVersion":"'+schema+'","dsn":'+json.dumps(dsn)+',"role":"'+role+'",'+extra+'}'
    else:
        text=json.dumps({'schemaVersion':schema,'dsn':dsn,'role':role})
    path.write_text(text,encoding='utf-8')
    path.chmod(0o600)
    return path


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv(ENV,raising=False)
    assert configured_eval_writer_connection() is None
    with pytest.raises(RuntimeError):
        with eval_writer_connection(expected_database="aos_bg00ad_schema_v2_20260929"):
            pass


@pytest.mark.parametrize("problem", ["permissions", "schema", "role", "duplicate", "symlink"])
def test_protected_identity_file_rejects_bad_shape(test_identity,tmp_path,monkeypatch,problem):
    _,writer=test_identity
    path=_file(tmp_path,writer,
        schema="wrong" if problem=="schema" else SCHEMA,
        role="aos_runtime" if problem=="role" else ROLE,
        extra='"role":"'+ROLE+'"' if problem=="duplicate" else "")
    if problem=="permissions": path.chmod(0o644)
    if problem=="symlink":
        link=tmp_path/'identity-link.json'
        link.symlink_to(path)
        path=link
    monkeypatch.setenv(ENV,str(path))
    with pytest.raises(RuntimeError):
        with eval_writer_connection(expected_database="aos_bg00ad_schema_v2_20260929"):
            pass


def test_extra_reachable_role_is_rejected(test_identity,tmp_path,monkeypatch):
    admin,writer=test_identity
    path=_file(tmp_path,writer)
    monkeypatch.setenv(ENV,str(path))
    extra='aos_bg00ah_extra_role'
    with psycopg.connect(admin,autocommit=True) as conn:
        if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(extra,)).fetchone():
            conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION').format(sql.Identifier(extra)))
        conn.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(extra),sql.Identifier(LOGIN)))
    try:
        with pytest.raises(RuntimeError):
            with eval_writer_connection(expected_database='aos_bg00ad_schema_v2_20260929'):
                pass
    finally:
        with psycopg.connect(admin,autocommit=True) as conn:
            conn.execute(sql.SQL('REVOKE {} FROM {}').format(sql.Identifier(extra),sql.Identifier(LOGIN)))


def test_test_only_independent_login_passes_but_superuser_fails(test_identity,tmp_path,monkeypatch):
    admin,writer=test_identity
    path=_file(tmp_path,writer)
    monkeypatch.setenv(ENV,str(path))
    assert configured_eval_writer_connection() is eval_writer_connection
    with eval_writer_connection(expected_database="aos_bg00ad_schema_v2_20260929") as conn:
        row=conn.execute('SELECT session_user,current_user').fetchone()
        assert tuple(row.values()) == (LOGIN,LOGIN)
        assert conn.execute("SELECT has_table_privilege(%s,'aip_eval_execution_receipt','INSERT')",
                            (ROLE,)).fetchone()['has_table_privilege'] is False
    with pytest.raises(RuntimeError):
        with eval_writer_connection(expected_database="wrong_database"):
            pass
    path=_file(tmp_path,admin)
    with pytest.raises(RuntimeError):
        with eval_writer_connection(expected_database="aos_bg00ad_schema_v2_20260929"):
            pass
