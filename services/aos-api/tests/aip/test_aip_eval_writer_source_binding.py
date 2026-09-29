"""A signed Report still needs persisted Dataset and canonical Suite authority."""
from __future__ import annotations

import psycopg
import pytest

from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from test_aip_eval_writer_atomic import isolated_writer, _write


@pytest.mark.parametrize("isolated_writer,counts", [
    ("missing", (0, 0)), ("missing_dataset", (0, 1)),
    ("missing_suite", (1, 0)), ("wrong_dataset_hash", (1, 1)),
    ("wrong_suite_hash", (1, 1)),
    ("wrong_case", (1, 1)),
], indirect=["isolated_writer"])
def test_missing_or_drifted_source_rejects_before_receipts(isolated_writer, counts):
    admin_dsn, report, target, judge = isolated_writer
    with psycopg.connect(admin_dsn) as conn:
        assert (
            conn.execute("SELECT count(*) FROM aip_eval_dataset_revision").fetchone()[0],
            conn.execute("SELECT count(*) FROM aip_eval_suite_revision").fetchone()[0],
        ) == counts
    with pytest.raises(EvalExecutionRejected):
        _write(report, target, judge)
    with psycopg.connect(admin_dsn) as conn:
        assert conn.execute("SELECT count(*) FROM aip_eval_execution_receipt").fetchone()[0] == 0
