"""Rollback-only current-authority preflight under the isolated Eval writer."""
from __future__ import annotations

import os

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import PresentedEvalCaseProof
from aos_api.aip_eval_writer_authority_preflight import preflight_skill_eval_writer_authority
from test_aip_eval_execution_authority import INPUT_HASH, NOW, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_report_proof_reader import _report
from test_aip_eval_writer_transaction import _grant_isolated


@pytest.fixture()
def connection():
    dsn = os.getenv("AOS_BG00AJ_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("isolated BG-00aj PostgreSQL URL required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "aos_bg00ad_schema_v2_20260929"
        assert conn.info.port == 5433
        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        yield conn
        conn.rollback()


def _proof(target, judge):
    return PresentedEvalCaseProof(
        target_certificate=target[0], target_receipt=target[1],
        judge_certificate=judge[0], judge_receipt=judge[1],
    )


def _read(conn, report, target, judge):
    return preflight_skill_eval_writer_authority(
        conn, report=report, evaluated_at=NOW,
        expected_input_hashes={"case-1": INPUT_HASH},
        presented={"case-1": _proof(target, judge)},
    )


@pytest.mark.parametrize("scenario", [
    "valid", "no_authority", "revoked", "root_revoked", "bad_signature",
    "wrong_role", "wrong_tenant", "wrong_input", "missing_case", "wrong_isolation",
    "run_not_succeeded",
])
def test_writer_preflight_uses_current_authority_before_insert(connection, scenario):
    root, target, judge = _signed_pair()
    report = _report()
    if scenario != "no_authority":
        _seed(connection, root, target, judge, stage="identities")
        connection.execute("""UPDATE aip_eval_run SET status='succeeded',
            target_ref=%s,dataset_ref=%s,judge_ref=%s
            WHERE run_id='run-1'""", (
            Jsonb(report.target.model_dump(mode="json", by_alias=True)),
            Jsonb(report.dataset.model_dump(mode="json", by_alias=True)),
            Jsonb(report.judge.model_dump(mode="json", by_alias=True)),
        ))
    _grant_isolated(connection)
    if scenario == "revoked":
        connection.execute("""INSERT INTO aip_eval_authority_revocation
            (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
             approval_ref,reason_hash)
            VALUES ('org-org','dev-project','bg00aj-revoke',%s,%s,%s,%s,%s)""",
            (target[0].identity_id, NOW, "test-owner", Jsonb({"testOnly": True}), "e"*64))
    if scenario == "root_revoked":
        connection.execute("""INSERT INTO aip_eval_authority_revocation
            (org_id,project_id,event_id,issuer_id,issuer_key_id,revoked_at,
             owner_ref,approval_ref,reason_hash)
            VALUES ('org-org','dev-project','bg00aj-root-revoke',%s,%s,%s,%s,%s,%s)""",
            (root.issuer_id, root.key_id, NOW, "test-owner", Jsonb({"testOnly": True}), "e"*64))
    if scenario == "bad_signature":
        target = (target[0], target[1].model_copy(update={"signature_base64": "AA=="}), target[2])
    if scenario == "run_not_succeeded":
        connection.execute("UPDATE aip_eval_run SET status='queued' WHERE run_id='run-1'")
    if scenario != "wrong_role":
        connection.execute("SET LOCAL ROLE aos_aip_eval_writer")
    connection.execute("SELECT set_config('aos.org_id',%s,true)",
                       ("dev-org" if scenario == "wrong_tenant" else "org-org",))
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    if scenario == "wrong_isolation":
        # A separate read-committed transaction proves the isolation guard.
        connection.rollback()
        connection.execute("SET LOCAL ROLE aos_aip_eval_writer")
        connection.execute("SELECT set_config('aos.org_id','org-org',true)")
        connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    if scenario == "valid":
        result = _read(connection, report, target, judge)
        assert result.report_id == report.report_id and len(result.cases) == 1
        assert result.cases[0].passed is True
        assert connection.execute("SELECT count(*) FROM aip_eval_execution_receipt").fetchone()[0] == 0
    else:
        with pytest.raises(EvalExecutionRejected):
            preflight_skill_eval_writer_authority(
                connection, report=report, evaluated_at=NOW,
                expected_input_hashes={"case-1": "f"*64} if scenario == "wrong_input"
                    else {} if scenario == "missing_case" else {"case-1": INPUT_HASH},
                presented={"case-1": _proof(target, judge)},
            )
