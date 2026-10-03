"""A dedicated BI Plan issuer keeps its own DB role while binding tenant GUCs."""

import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import pytest

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import get_dsn


def test_nonmember_issuer_preserves_identity_and_stays_database_denied():
    parts = conninfo_to_dict(get_dsn())
    assert parts["dbname"].startswith("aos_test_")
    assert parts["dbname"].endswith("_ti4_test")
    role = "s3own_bi_" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    with psycopg.connect(get_dsn(), autocommit=True) as admin:
        admin.execute(
            sql.SQL("""CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
                PASSWORD {}""").format(sql.Identifier(role), sql.Literal(password))
        )
        try:
            with psycopg.connect(
                host=parts["host"], port=parts["port"], dbname=parts["dbname"],
                user=role, password=password, row_factory=dict_row,
            ) as issuer:
                assert issuer.execute(
                    "SELECT pg_has_role(current_user,'aos_runtime','member') AS member"
                ).fetchone()["member"] is False
                apply_asset_transaction_scope(
                    issuer, org_id="org-org", project_id="dev-project",
                )
                row = issuer.execute(
                    """SELECT current_user AS current_user, session_user AS session_user,
                         current_setting('aos.org_id',true) AS org_id,
                         current_setting('aos.project_id',true) AS project_id"""
                ).fetchone()
                assert row == {
                    "current_user": role, "session_user": role,
                    "org_id": "org-org", "project_id": "dev-project",
                }
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    issuer.execute("SELECT 1 FROM bundle_installation LIMIT 1")
                issuer.rollback()
                assert issuer.execute(
                    "SELECT current_setting('aos.org_id',true) AS org_id"
                ).fetchone()["org_id"] in (None, "")
                admin.execute(sql.SQL("GRANT SELECT ON bundle_installation TO {}").format(
                    sql.Identifier(role)
                ))
                admin.execute(sql.SQL("""CREATE POLICY {} ON bundle_installation TO {}
                    USING (org_id=current_setting('aos.org_id',true)
                       AND project_id=current_setting('aos.project_id',true))""").format(
                    sql.Identifier(role + "_installation_read"), sql.Identifier(role)
                ))
                apply_asset_transaction_scope(
                    issuer, org_id="org-org", project_id="dev-project",
                )
                issuer.execute("SELECT 1 FROM bundle_installation LIMIT 1")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    issuer.execute("SELECT 1 FROM bundle_installation FOR UPDATE LIMIT 1")
                issuer.rollback()
        finally:
            admin.execute(sql.SQL("DROP POLICY IF EXISTS {} ON bundle_installation").format(
                sql.Identifier(role + "_installation_read")
            ))
            admin.execute(sql.SQL("REVOKE SELECT ON bundle_installation FROM {}").format(
                sql.Identifier(role)
            ))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
