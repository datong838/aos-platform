"""Real isolated-login atomic Eval persistence; committed test rows are cleaned."""
from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import PresentedEvalCaseProof
from aos_api.aip_eval_writer_atomic import persist_signed_skill_eval_report
from test_aip_eval_execution_authority import INPUT_HASH, NOW, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_report_proof_reader import _report, _seed_report
from test_aip_eval_writer_transaction import ROLE, TABLES, _grant_isolated

DB = "aos_bg00ad_schema_v2_20260929"
LOGIN = "aos_bg00ak_eval_writer_login"
ENV = "AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE"


@pytest.fixture()
def isolated_writer(tmp_path, monkeypatch):
    admin_dsn = os.getenv("AOS_BG00AK_TEST_ADMIN_URL")
    if not admin_dsn:
        pytest.skip("isolated BG-00ak PostgreSQL URL required")
    info = conninfo_to_dict(admin_dsn)
    assert info["dbname"] == DB and int(info["port"]) == 5433
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        for table in ("aip_eval_issuer_root", "aip_eval_executor_identity",
                      "aip_eval_authority_revocation", "aip_eval_execution_receipt",
                      "aip_eval_report_revision", "aip_eval_case_execution_proof"):
            assert admin.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (LOGIN,)).fetchone() is None
        admin.execute(sql.SQL("""CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER
            NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION PASSWORD {}""").format(
            sql.Identifier(LOGIN), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT {} TO {}").format(
            sql.Identifier(ROLE), sql.Identifier(LOGIN)))
    root, target, judge = _signed_pair(datetime.now(UTC))
    report = _report()
    with psycopg.connect(admin_dsn) as admin:
        _seed(admin, root, target, judge, stage="identities")
        admin.execute("""UPDATE aip_eval_run SET status='succeeded',
            target_ref=%s,dataset_ref=%s,judge_ref=%s WHERE run_id='run-1'""", (
            Jsonb(report.target.model_dump(mode="json", by_alias=True)),
            Jsonb(report.dataset.model_dump(mode="json", by_alias=True)),
            Jsonb(report.judge.model_dump(mode="json", by_alias=True)),
        ))
        _grant_isolated(admin)
        admin.commit()
    writer_dsn = make_conninfo(admin_dsn, user=LOGIN, password=password)
    identity = tmp_path / "eval-writer.json"
    identity.write_text(json.dumps({
        "schemaVersion": "aos.aip.eval-writer-identity/v1",
        "dsn": writer_dsn, "role": ROLE,
    }), encoding="utf-8")
    identity.chmod(0o600)
    monkeypatch.setenv(ENV, str(identity))
    try:
        yield admin_dsn, report, target, judge
    finally:
        monkeypatch.delenv(ENV, raising=False)
        with psycopg.connect(admin_dsn) as admin:
            append_only = ("aip_eval_case_execution_proof", "aip_eval_report_revision",
                           "aip_eval_execution_receipt", "aip_eval_authority_revocation",
                           "aip_eval_executor_identity", "aip_eval_issuer_root")
            # Test-only cleanup uses a single DDL+DML transaction. The normal
            # append-only trigger remains enabled if any cleanup statement fails.
            for table in append_only:
                admin.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(
                    sql.Identifier(table)))
            for table in (*append_only, "aip_eval_run"):
                admin.execute("DELETE FROM " + table +
                              " WHERE org_id='org-org' AND project_id='dev-project'")
            for table in append_only:
                admin.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(
                    sql.Identifier(table)))
            for table in TABLES:
                admin.execute("DROP POLICY bg00ai_test_writer_" + table + " ON " + table)
                admin.execute("REVOKE SELECT ON " + table + " FROM " + ROLE)
            for table in ("aip_eval_execution_receipt", "aip_eval_report_revision",
                          "aip_eval_case_execution_proof"):
                admin.execute("REVOKE INSERT ON " + table + " FROM " + ROLE)
            admin.commit()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(ROLE), sql.Identifier(LOGIN)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(LOGIN)))
        with psycopg.connect(admin_dsn) as admin:
            assert admin.execute("SELECT count(*) FROM aip_eval_execution_receipt").fetchone()[0] == 0
            assert admin.execute("SELECT count(*) FROM aip_eval_report_revision").fetchone()[0] == 0
            assert admin.execute("SELECT count(*) FROM aip_eval_case_execution_proof").fetchone()[0] == 0


def _presented(target, judge):
    return {"case-1": PresentedEvalCaseProof(
        target_certificate=target[0], target_receipt=target[1],
        judge_certificate=judge[0], judge_receipt=judge[1],
    )}


def _write(report, target, judge):
    return persist_signed_skill_eval_report(
        expected_database=DB, report=report,
        expected_input_hashes={"case-1": INPUT_HASH},
        presented=_presented(target, judge),
    )


def test_independent_writer_commits_double_receipt_report_and_sidecar(isolated_writer):
    admin_dsn, report, target, judge = isolated_writer
    result = _write(report, target, judge)
    assert result.report_id == report.report_id and len(result.cases) == 1
    with psycopg.connect(admin_dsn) as admin:
        assert [admin.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in (
            "aip_eval_execution_receipt", "aip_eval_report_revision",
            "aip_eval_case_execution_proof",
        )] == [2, 1, 1]


def test_report_conflict_rolls_back_new_receipts_and_sidecar(isolated_writer):
    admin_dsn, report, target, judge = isolated_writer
    with psycopg.connect(admin_dsn) as admin:
        _seed_report(admin, report)
        admin.commit()
    with pytest.raises(EvalExecutionRejected):
        _write(report, target, judge)
    with psycopg.connect(admin_dsn) as admin:
        assert [admin.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in (
            "aip_eval_execution_receipt", "aip_eval_report_revision",
            "aip_eval_case_execution_proof",
        )] == [0, 1, 0]


def test_bad_signature_rejects_before_any_insert(isolated_writer):
    admin_dsn, report, target, judge = isolated_writer
    target = (target[0], target[1].model_copy(update={"signature_base64": "AA=="}), target[2])
    with pytest.raises(EvalExecutionRejected):
        _write(report, target, judge)
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT count(*) FROM aip_eval_execution_receipt").fetchone()[0] == 0


def test_missing_writer_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    _, target, judge = _signed_pair()
    with pytest.raises(EvalExecutionRejected):
        _write(_report(), target, judge)
