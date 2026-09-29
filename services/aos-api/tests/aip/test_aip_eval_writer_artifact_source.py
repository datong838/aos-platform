"""An exact Dataset alone cannot certify current Artifact snapshot metadata."""
from __future__ import annotations

import psycopg
import pytest

from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from test_aip_eval_writer_atomic import isolated_writer, _write


@pytest.mark.parametrize("isolated_writer", ["artifact_missing", "artifact_bad_hash",
    "artifact_bad_link", "artifact_empty_ref"], indirect=True)
def test_artifact_snapshot_missing_or_drifted_rejects_before_receipts(isolated_writer):
    admin_dsn, report, target, judge = isolated_writer
    with pytest.raises(EvalExecutionRejected):
        _write(report, target, judge)
    with psycopg.connect(admin_dsn) as conn:
        assert [conn.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in (
            "aip_eval_execution_receipt", "aip_eval_report_revision",
            "aip_eval_case_execution_proof")] == [0, 0, 0]


@pytest.mark.parametrize("isolated_writer", ["artifact_valid"], indirect=True)
def test_exact_artifact_snapshot_metadata_permits_signed_proof(isolated_writer):
    admin_dsn, report, target, judge = isolated_writer
    _write(report, target, judge)
    with psycopg.connect(admin_dsn) as conn:
        assert [conn.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in (
            "aip_eval_execution_receipt", "aip_eval_report_revision",
            "aip_eval_case_execution_proof")] == [2, 1, 1]
