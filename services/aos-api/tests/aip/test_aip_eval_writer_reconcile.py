"""Real test-only persistence followed by independent read-only reconciliation."""
from __future__ import annotations

from datetime import UTC, datetime

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_writer_reconcile import reconcile_signed_skill_eval_report
from test_aip_eval_execution_authority import INPUT_HASH
from test_aip_eval_report_proof_reader import _seed_report
from test_aip_eval_writer_atomic import isolated_writer, _presented, _write


def _reconcile(admin_dsn, report, target, judge, *, tenant="org-org", role=True,
               read_only=True, bad_input=False):
    with psycopg.connect(admin_dsn) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ " +
                     ("READ ONLY" if read_only else "READ WRITE"))
        if role:
            conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (tenant,))
        conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
        return reconcile_signed_skill_eval_report(
            conn, report=report,
            expected_input_hashes={"case-1": "f"*64 if bad_input else INPUT_HASH},
            presented=_presented(target, judge),
        )


def test_complete_only_after_exact_committed_proof(isolated_writer):
    admin_dsn, report, target, judge = isolated_writer
    assert _reconcile(admin_dsn, report, target, judge).state == "UNKNOWN"
    _write(report, target, judge)
    result = _reconcile(admin_dsn, report, target, judge)
    assert result.state == "COMPLETE" and result.proof is not None
    assert result.proof.report_id == report.report_id


@pytest.mark.parametrize("scenario", [
    "partial", "cross_tenant", "wrong_role", "write_transaction", "wrong_input",
    "revoked",
])
def test_unknown_never_authorizes_resend(isolated_writer, scenario):
    admin_dsn, report, target, judge = isolated_writer
    if scenario == "partial":
        with psycopg.connect(admin_dsn) as conn:
            _seed_report(conn, report)
            conn.commit()
    else:
        _write(report, target, judge)
    if scenario == "revoked":
        with psycopg.connect(admin_dsn) as conn:
            conn.execute("""INSERT INTO aip_eval_authority_revocation
                (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
                 approval_ref,reason_hash)
                VALUES ('org-org','dev-project','bg00al-revoked',%s,%s,%s,%s,%s)""",
                (target[0].identity_id, datetime.now(UTC), "test-owner",
                 Jsonb({"testOnly": True}), "e"*64))
            conn.commit()
    result = _reconcile(
        admin_dsn, report, target, judge,
        tenant="dev-org" if scenario == "cross_tenant" else "org-org",
        role=scenario != "wrong_role",
        read_only=scenario != "write_transaction",
        bad_input=scenario == "wrong_input",
    )
    assert result.state == "UNKNOWN" and result.proof is None
