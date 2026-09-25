"""The canonical witness sidecar starts empty, immutable, and uncallable."""

import os

import psycopg
import pytest

from aos_api.pipeline_snapshot_group_canonical_witness import reconstruct_witness

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)


TABLE = "public.pipeline_snapshot_group_canonical_witness_a0v_097"
OLD_RECONCILE = (
    "public.data_requirement_outbox_reconcile_completed_a0v_050"
    "(text,bigint,text,jsonb,jsonb)"
)
NORMAL_COMPLETE = (
    "public.data_requirement_outbox_complete_a0v_050"
    "(text,bigint,text,jsonb,jsonb)"
)


def test_empty_witness_sidecar_has_no_runtime_write_grant():
    with psycopg.connect(os.environ["AOS_DATABASE_URL"], autocommit=True) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        assert conn.execute("SELECT to_regclass(%s) IS NOT NULL", (TABLE,)).fetchone()[0]
        assert conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
        for role in ("aos_runtime", "aos_extension_directory", "aos_extension_maintainer"):
            assert conn.execute("SELECT has_table_privilege(%s,%s,'INSERT')",
                                (role, TABLE)).fetchone()[0] is False
            assert conn.execute("SELECT has_table_privilege(%s,%s,'UPDATE')",
                                (role, TABLE)).fetchone()[0] is False
        assert conn.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE')",
                            (OLD_RECONCILE,)).fetchone()[0] is False
        assert conn.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE')",
                            (NORMAL_COMPLETE,)).fetchone()[0] is True

        names = {row[0] for row in conn.execute("""SELECT tgname FROM pg_trigger
            WHERE tgrelid=%s::regclass AND NOT tgisinternal""", (TABLE,))}
        assert {"immutable_history", "immutable_truncate"} <= names
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id','org-org',false),"
                     "set_config('aos.project_id','dev-project',false)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(f"""INSERT INTO {TABLE}
                (org_id,project_id,group_id,request_hash,manifest_hash,
                 binding_canonical_json,manifest_canonical_json)
                VALUES ('org-org','dev-project','00000000-0000-4000-8000-000000000001',
                    'sha256:'||repeat('0',64),'sha256:'||repeat('0',64),'{{}}','{{}}')""")
        conn.execute("RESET ROLE")
        assert conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_original_group_sidecar_insert_is_immutable_and_cannot_be_forged(chain_case):
    conn, state, analysis, _session, _root, _requirement = chain_case
    run_id = analysis.source.reader._journal._run_id
    rows = conn.execute("""SELECT c.group_id,c.request_hash,c.binding,
            i.manifest_hash,i.manifest
        FROM pipeline_snapshot_group_member m
        JOIN pipeline_snapshot_group_claim c USING(org_id,project_id,group_id)
        JOIN pipeline_snapshot_group_input i USING(org_id,project_id,group_id)
        WHERE m.org_id=%s AND m.project_id=%s AND m.run_id=%s""",
        (*analysis.scope.key, run_id)).fetchall()
    assert len(rows) == 1
    row = rows[0]
    witness = reconstruct_witness(row["binding"], row["request_hash"],
                                  row["manifest"], row["manifest_hash"])
    with psycopg.connect(os.environ["AOS_DATABASE_URL"], autocommit=True) as admin:
        admin.execute("SELECT set_config('aos.org_id',%s,false),"
                      "set_config('aos.project_id',%s,false)", analysis.scope.key)
        admin.execute(f"""INSERT INTO {TABLE}
            (org_id,project_id,group_id,request_hash,manifest_hash,
             binding_canonical_json,manifest_canonical_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (*analysis.scope.key, row["group_id"], row["request_hash"],
             row["manifest_hash"], witness.binding_json, witness.manifest_json))
        assert admin.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1
        for statement in (
            f"UPDATE {TABLE} SET binding_canonical_json=binding_canonical_json",
            f"DELETE FROM {TABLE}",
            f"TRUNCATE {TABLE}",
        ):
            with pytest.raises(psycopg.Error, match="immutable"):
                admin.execute(statement)
        with pytest.raises(psycopg.Error):
            admin.execute(f"""INSERT INTO {TABLE}
                (org_id,project_id,group_id,request_hash,manifest_hash,
                 binding_canonical_json,manifest_canonical_json)
                VALUES (%s,%s,'00000000-0000-4000-8000-000000000001',%s,%s,%s,%s)""",
                (*analysis.scope.key, row["request_hash"], row["manifest_hash"],
                 witness.binding_json, witness.manifest_json))
        assert admin.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1
    assert state["calls"] == 1
