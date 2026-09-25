"""A dedicated witness role/function is inert until separately authorized."""

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from aos_api.pipeline_snapshot_group_canonical_witness import reconstruct_witness
from test_a0v_w5c8n_bounded_group_report_pg import _insert_synthetic_missing_input_group

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)


ROLE = "aos_snapshot_witness_backfill"
FUNCTION_NAME = "public.pipeline_snapshot_group_witness_backfill_a0v_098"
FUNCTION = FUNCTION_NAME + "(text,text,uuid,text,text)"
TABLE = "public.pipeline_snapshot_group_canonical_witness_a0v_097"


def test_dedicated_witness_role_and_function_are_not_runtime_authority(private_database):
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        role = conn.execute("""SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit,
            rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s""",
            (ROLE,)).fetchone()
        assert role == (False, False, False, False, False, False, False)
        assert conn.execute("SELECT to_regprocedure(%s) IS NOT NULL", (FUNCTION,)).fetchone()[0]
        assert conn.execute("""SELECT r.rolname FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
            WHERE p.oid=to_regprocedure(%s)""", (FUNCTION,)).fetchone()[0] == ROLE
        assert conn.execute("""SELECT count(*) FROM pg_auth_members
            WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname=%s)""",
            (ROLE,)).fetchone()[0] == 0
        for identity in ("aos_runtime", "aos_extension_directory",
                         "aos_extension_maintainer"):
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'INSERT')",
                                    (identity, TABLE)).fetchone()[0]
            assert not conn.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",
                                    (identity, FUNCTION)).fetchone()[0]
        assert not conn.execute("SELECT has_table_privilege(%s,%s,'INSERT')",
                                ("aos_snapshot_witness_operator", TABLE)).fetchone()[0]
        assert conn.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",
                            (ROLE, FUNCTION)).fetchone()[0] is True


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_exact_operator_binds_original_input_without_direct_table_write(chain_case):
    conn, state, analysis, _session, _root, _requirement = chain_case
    conn.rollback()
    dsn = os.environ["AOS_DATABASE_URL"]
    assert psycopg.conninfo.conninfo_to_dict(dsn)["dbname"] == conn.info.dbname
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        row = admin.execute("""SELECT c.group_id,c.request_hash,c.binding,
            i.manifest_hash,i.manifest FROM pipeline_snapshot_group_claim c
            JOIN pipeline_snapshot_group_input i USING(org_id,project_id,group_id)
            WHERE c.org_id=%s AND c.project_id=%s""", analysis.scope.key).fetchone()
        assert row is not None
    witness = reconstruct_witness(row["binding"], row["request_hash"],
                                  row["manifest"], row["manifest_hash"])
    missing_input_group = _insert_synthetic_missing_input_group(conn, analysis.scope, ordinal=2)
    caller = "aos_test_witness_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT")
                      .format(sql.Identifier(caller)))
        admin.execute(sql.SQL("GRANT aos_snapshot_witness_operator TO {}")
                      .format(sql.Identifier(caller)))
        try:
            with psycopg.connect(dsn, row_factory=dict_row) as operator:
                operator.execute(sql.SQL("SET SESSION AUTHORIZATION {}")
                                 .format(sql.Identifier(caller)))
                operator.execute("SET ROLE aos_snapshot_witness_operator")
                operator.execute("SELECT set_config('aos.org_id',%s,false),"
                                 "set_config('aos.project_id',%s,false)", analysis.scope.key)
                operator.commit()
                operator.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                assert operator.execute("SELECT has_table_privilege(%s,'INSERT') AS allowed",
                                        (TABLE,)).fetchone()["allowed"] is False
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    operator.execute(f"INSERT INTO {TABLE} DEFAULT VALUES")
                operator.rollback()
                args = (*analysis.scope.key, row["group_id"],
                        witness.binding_json, witness.manifest_json)
                barrier = Barrier(2)

                def compete():
                    with psycopg.connect(dsn, row_factory=dict_row) as contender:
                        contender.execute(sql.SQL("SET SESSION AUTHORIZATION {}")
                                          .format(sql.Identifier(caller)))
                        contender.execute("SET ROLE aos_snapshot_witness_operator")
                        contender.execute("SELECT set_config('aos.org_id',%s,false),"
                                          "set_config('aos.project_id',%s,false)", analysis.scope.key)
                        contender.commit()
                        contender.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                        contender.execute("SELECT pg_current_snapshot()")
                        barrier.wait(timeout=10)
                        try:
                            result = contender.execute(f"SELECT {FUNCTION_NAME}"
                                "(%s,%s,%s,%s,%s) AS result", args).fetchone()["result"]
                            contender.commit()
                            return result
                        except psycopg.errors.SerializationFailure:
                            contender.rollback()
                            return "SERIALIZATION_FAILURE"

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda _: compete(), range(2)))
                assert outcomes.count("INSERTED") == 1
                assert set(outcomes) <= {"INSERTED", "ALREADY_PRESENT", "SERIALIZATION_FAILURE"}
                operator.commit()
                assert operator.execute(f"SELECT {FUNCTION_NAME}"
                                        "(%s,%s,%s,%s,%s) AS result", args).fetchone()["result"] == "ALREADY_PRESENT"
                operator.commit()
                with pytest.raises(psycopg.Error):
                    operator.execute(f"SELECT {FUNCTION_NAME}"
                                     "(%s,%s,%s,%s,%s)", (*args[:-1], "{}"))
                operator.rollback()
                with pytest.raises(psycopg.Error):
                    operator.execute(f"SELECT {FUNCTION_NAME}"
                                     "(%s,%s,%s,%s,%s)",
                                     (*args[:3], witness.binding_json + " ", witness.manifest_json))
                operator.rollback()
                with pytest.raises(psycopg.Error):
                    operator.execute(f"SELECT {FUNCTION_NAME}"
                                     "(%s,%s,%s,%s,%s)",
                                     (*analysis.scope.key, missing_input_group,
                                      witness.binding_json, witness.manifest_json))
                operator.rollback()
                with pytest.raises(psycopg.Error):
                    operator.execute(f"SELECT {FUNCTION_NAME}"
                                     "(%s,%s,%s,%s,%s)", ("dev-org", *args[1:]))
                operator.rollback()
            assert admin.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1
        finally:
            admin.execute(sql.SQL("REVOKE aos_snapshot_witness_operator FROM {}")
                          .format(sql.Identifier(caller)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(caller)))
    assert state["calls"] == 1
