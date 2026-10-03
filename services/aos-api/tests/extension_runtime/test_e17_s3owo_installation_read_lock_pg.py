"""Disposable PG proof for a narrow installation lock callable by a BI issuer."""

import secrets
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from test_lifecycle_pg import database, pytestmark


def test_read_only_issuer_locks_exact_installation_without_update_grant(database):
    owner, _, schema = database
    role = "s3owo_bi_" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    installation = uuid4()
    owner.execute(
        "INSERT INTO bundle_installation(org_id,project_id,installation_id) "
        "VALUES('org-org','dev-project',%s)", (installation,)
    )
    owner.execute(sql.SQL("""CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
        PASSWORD {}""").format(sql.Identifier(role), sql.Literal(password)))
    try:
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(schema), sql.Identifier(role)))
        owner.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
            sql.Identifier(schema, "bundle_installation"), sql.Identifier(role)))
        owner.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
            sql.Identifier(schema, "bundle_installation")))
        owner.execute(sql.SQL("""CREATE POLICY s3owo_issuer_read ON {} TO {}
            USING (org_id=current_setting('aos.org_id',true)
               AND project_id=current_setting('aos.project_id',true))""").format(
            sql.Identifier(schema, "bundle_installation"), sql.Identifier(role)))
        target = ("org-org", "dev-project", installation)
        with psycopg.connect(host="127.0.0.1", port=18432, dbname="postgres",
                             user=role, password=password) as issuer:
            issuer.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            issuer.execute("SELECT set_config('aos.org_id','org-org',true),"
                           "set_config('aos.project_id','dev-project',true)")
            assert issuer.execute(
                "SELECT etag_version FROM bundle_installation WHERE org_id=%s "
                "AND project_id=%s AND installation_id=%s", target,
            ).fetchone() == (1,)
            # RED: direct row locks demand UPDATE privilege even for FOR SHARE.
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                issuer.execute("SELECT etag_version FROM bundle_installation "
                               "WHERE org_id=%s AND project_id=%s AND installation_id=%s "
                               "FOR SHARE", target)
            issuer.rollback()

            owner.execute(sql.SQL("""CREATE FUNCTION {}(p_org text,p_project text,
                p_installation uuid,p_etag bigint) RETURNS bigint
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                DECLARE actual bigint;
                BEGIN
                  IF session_user<>{} OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
                    RAISE EXCEPTION 'installation unavailable' USING ERRCODE='42501';
                  END IF;
                  SELECT etag_version INTO actual FROM {}
                    WHERE org_id=p_org AND project_id=p_project
                      AND installation_id=p_installation FOR UPDATE;
                  IF actual IS DISTINCT FROM p_etag THEN
                    RAISE EXCEPTION 'installation unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN actual;
                END $$""").format(
                    sql.Identifier(schema, "s3owo_lock_installation"), sql.Literal(role),
                    sql.Identifier(schema, "bundle_installation")))
            signature = sql.SQL("{}(text,text,uuid,bigint)").format(
                sql.Identifier(schema, "s3owo_lock_installation"))
            owner.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC").format(signature))
            owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                signature, sql.Identifier(role)))
            call = sql.SQL("SELECT {}(%s,%s,%s,%s)").format(
                sql.Identifier(schema, "s3owo_lock_installation"))
            for scope, etag in (("dev-org", 1), ("org-org", 2)):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    issuer.execute(call, (scope, "dev-project", installation, etag))
                issuer.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                issuer.execute(sql.SQL("UPDATE {} SET etag_version=2 WHERE "
                    "installation_id=%s").format(
                        sql.Identifier(schema, "bundle_installation")), (installation,))
            issuer.rollback()

            with psycopg.connect(host="127.0.0.1", port=18432, dbname="postgres",
                                 user="postgres", autocommit=True) as writer:
                writer.execute("SELECT set_config('aos.org_id','org-org',false),"
                               "set_config('aos.project_id','dev-project',false)")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    writer.execute(call, (*target, 1))
                with issuer.transaction():
                    issuer.execute("SELECT set_config('aos.org_id','org-org',true),"
                                   "set_config('aos.project_id','dev-project',true)")
                    assert issuer.execute(call, (*target, 1)).fetchone() == (1,)
                    writer.execute("SET lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        writer.execute(sql.SQL("UPDATE {} SET etag_version=2 WHERE "
                            "org_id=%s AND project_id=%s AND installation_id=%s").format(
                                sql.Identifier(schema, "bundle_installation")), target)
                assert writer.execute(sql.SQL("UPDATE {} SET etag_version=2 WHERE "
                    "org_id=%s AND project_id=%s AND installation_id=%s").format(
                        sql.Identifier(schema, "bundle_installation")), target).rowcount == 1
            issuer.execute("SELECT set_config('aos.org_id','org-org',true),"
                           "set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                issuer.execute(call, (*target, 1))
            issuer.rollback()
        assert owner.execute("SELECT etag_version FROM bundle_installation "
                             "WHERE installation_id=%s", (installation,)).fetchone() == (2,)
    finally:
        owner.execute(sql.SQL("DROP POLICY IF EXISTS s3owo_issuer_read ON {}").format(
            sql.Identifier(schema, "bundle_installation")))
        owner.execute(sql.SQL("DROP FUNCTION IF EXISTS {}(text,text,uuid,bigint)").format(
            sql.Identifier(schema, "s3owo_lock_installation")))
        owner.execute(sql.SQL("REVOKE SELECT ON {} FROM {}").format(
            sql.Identifier(schema, "bundle_installation"), sql.Identifier(role)))
        owner.execute(sql.SQL("REVOKE USAGE ON SCHEMA {} FROM {}").format(
            sql.Identifier(schema), sql.Identifier(role)))
        owner.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
