"""Rollback-only proof assembly from original persisted Skill Eval sources."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import read_verified_skill_eval_report_from_persistence
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.db import get_dsn
from test_aip_eval_execution_authority import _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_report_proof_reader import _seed_report, _seed_sidecar
from test_aip_eval_writer_atomic import _seed_source, _source_objects


@pytest.mark.parametrize("scenario", [
    "valid", "wrong_suite_hash", "missing_sidecar", "revoked",
    "cross_tenant", "read_committed",
])
def test_signed_skill_report_assembles_only_exact_persisted_sources(scenario):
    suite, base_report = _source_objects()
    now = datetime.now(UTC)
    report = base_report.model_copy(update={"created_at": now})
    report = report.model_copy(update={"content_hash": compute_eval_report_hash(report)})
    root, target, judge = _signed_pair(now, suite_ref=report.suite_ref)
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        try:
            if scenario != "read_committed":
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            conn.execute("INSERT INTO twa_org(id,name) VALUES ('org-org','isolated') ON CONFLICT DO NOTHING")
            conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
                VALUES ('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
            _seed_source(conn, suite, suite_hash_override="f" * 64 if scenario == "wrong_suite_hash" else None)
            _seed(conn, root, target, judge, suite_ref=report.suite_ref)
            _seed_report(conn, report)
            if scenario != "missing_sidecar":
                _seed_sidecar(conn, target, judge)
            if scenario == "revoked":
                conn.execute("""INSERT INTO aip_eval_authority_revocation
                    (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
                     approval_ref,reason_hash)
                    VALUES ('org-org','dev-project','e17-s1-revoked',%s,%s,%s,%s,%s)""",
                    (target[0].identity_id, now, "isolated-test-owner",
                     Jsonb({"testOnly": True}), "e" * 64))
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)",
                         ("dev-org" if scenario == "cross_tenant" else "org-org",))
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            if scenario != "valid":
                with pytest.raises(EvalExecutionRejected):
                    read_verified_skill_eval_report_from_persistence(
                        conn, report=report, evaluated_at=now,
                    )
            else:
                proof = read_verified_skill_eval_report_from_persistence(
                    conn, report=report, evaluated_at=now,
                )
                assert proof.report_hash == report.content_hash
                assert len(proof.cases) == 1
        finally:
            conn.rollback()
