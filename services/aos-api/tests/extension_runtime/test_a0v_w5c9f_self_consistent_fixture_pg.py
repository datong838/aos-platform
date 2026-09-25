"""An immutable, hash-consistent original can still carry wrong row semantics."""

import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.ec_ingress_journal import _digest
from test_a0v_w5c8n_bounded_group_report_pg import _insert_synthetic_missing_input_group

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_immutable_synthetic_group_can_commit_hash_consistent_wrong_row_claim(chain_case):
    conn, _state, analysis, _session, _root, _requirement = chain_case
    conn.rollback()
    dsn = os.environ["AOS_DATABASE_URL"]
    assert psycopg.conninfo.conninfo_to_dict(dsn)["dbname"].startswith("aos_test_")
    group_id = _insert_synthetic_missing_input_group(conn, analysis.scope, ordinal=2)
    run_id = "fixture-report-2"
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        original = admin.execute("""SELECT i.envelope_hash,g.manifest,
            g.read_started_at,g.read_completed_at FROM ecommerce_ingress_command i
            JOIN pipeline_snapshot_group_member m ON
              (m.org_id,m.project_id,m.run_id)=(i.org_id,i.project_id,i.run_id)
            JOIN pipeline_snapshot_group_input g ON
              (g.org_id,g.project_id,g.group_id)=(m.org_id,m.project_id,m.group_id)
            WHERE i.org_id=%s AND i.project_id=%s AND i.run_id='fixture-original'""",
            analysis.scope.key).fetchone()
        assert original is not None
        old_member = next(item for item in original["manifest"]["members"]
                          if item["runId"] == "fixture-original")
        wrong_count = (old_member["rowCount"] + 1) % 1000
        wrong_hash = "sha256:" + "0" * 64
        assert wrong_hash != old_member["rowsHash"]
        admin.execute("""INSERT INTO ecommerce_ingress_command
            (org_id,project_id,run_id,pipeline_id,source_id,source_revision,
             envelope_hash,envelope)
            SELECT org_id,project_id,%s,pipeline_id,source_id,source_revision,
              envelope_hash,envelope FROM ecommerce_ingress_command
            WHERE org_id=%s AND project_id=%s AND run_id='fixture-original'""",
            (run_id, *analysis.scope.key))
        claim = admin.execute("""SELECT request_hash FROM pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s AND group_id=%s""",
            (*analysis.scope.key, group_id)).fetchone()
        manifest = {"members": [{"runId": run_id,
                                 "envelopeHash": original["envelope_hash"],
                                 "rowsHash": wrong_hash, "rowCount": wrong_count}]}
        admin.execute("""INSERT INTO pipeline_snapshot_group_input
            (org_id,project_id,group_id,request_hash,read_started_at,
             read_completed_at,snapshot_basis,manifest_hash,manifest)
            VALUES(%s,%s,%s,%s,%s,%s,'innodb-repeatable-read',%s,%s)""",
            (*analysis.scope.key, group_id, claim["request_hash"],
             original["read_started_at"], original["read_completed_at"],
             "sha256:" + _digest(manifest), Jsonb(manifest)))
    with psycopg.connect(dsn, row_factory=dict_row) as reader:
        saved = reader.execute("""SELECT manifest,manifest_hash FROM pipeline_snapshot_group_input
            WHERE org_id=%s AND project_id=%s AND group_id=%s""",
            (*analysis.scope.key, group_id)).fetchone()
        assert saved["manifest"] == manifest
        assert saved["manifest_hash"] == "sha256:" + _digest(manifest)
        assert reader.execute("""SELECT count(*) AS n FROM
            pipeline_snapshot_group_canonical_witness_a0v_097
            WHERE org_id=%s AND project_id=%s AND group_id=%s""",
            (*analysis.scope.key, group_id)).fetchone()["n"] == 0
