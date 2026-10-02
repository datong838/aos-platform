"""Isolated signed Skill Eval evidence must gate the original publication path."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.aip_eval_contracts import ReleaseGateStatus
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest, PublishReleaseRequest
from aos_api.aip_release_publication_service import (
    AipReleaseGateRejected, AipReleasePublicationNotFound,
    AipReleasePublicationService,
)
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from test_aip_eval_execution_authority import _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_report_proof_reader import _seed_report, _seed_sidecar
from test_aip_eval_writer_atomic import _seed_source, _source_objects


@pytest.fixture(autouse=True)
def cleanup_signed_skill_fixture():
    yield
    with psycopg.connect(get_dsn()) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        assert conn.info.dbname.endswith("_ti4_test")
        tables = (
            "aip_publication_event", "aip_release_gate_decision",
            "aip_eval_case_execution_proof", "aip_eval_execution_receipt",
            "aip_eval_report_revision", "aip_eval_authority_revocation",
            "aip_eval_run", "aip_eval_executor_identity", "aip_eval_issuer_root",
            "aip_eval_suite_revision", "aip_eval_dataset_revision",
        )
        for table in tables:
            conn.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(sql.Identifier(table)))
            conn.execute(sql.SQL("DELETE FROM {} WHERE org_id=%s AND project_id=%s").format(
                sql.Identifier(table)), ("org-org", "dev-project"))
            conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(sql.Identifier(table)))
        conn.commit()


def test_signed_skill_gate_derives_and_current_revocation_blocks_publish():
    scope = TenantScope("org-org", "dev-project")
    suite, base = _source_objects()
    now = datetime.now(UTC)
    report = base.model_copy(update={"created_at": now})
    report = report.model_copy(update={"content_hash": compute_eval_report_hash(report)})
    root, target, judge = _signed_pair(now, suite_ref=report.suite_ref)
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES ('org-org','isolated') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
            VALUES ('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
        _seed_source(conn, suite)
        _seed(conn, root, target, judge, suite_ref=report.suite_ref)
        _seed_report(conn, report)
        _seed_sidecar(conn, target, judge)
        conn.commit()

    service = AipReleasePublicationService()
    request = DeriveReleaseGateRequest(
        report_id=report.report_id, report_revision=report.revision,
        report_hash=report.content_hash, idempotency_key="e17-s2-signed-gate",
    )
    gate = service.derive_gate(scope, actor="isolated-test-actor", request=request)
    assert gate.status is ReleaseGateStatus.PASSED
    assert gate.eval_report.content_hash == report.content_hash
    with pytest.raises(AipReleasePublicationNotFound, match="skill template revision not found"):
        service.publish(scope, actor="isolated-test-actor", request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash="f" * 64, idempotency_key="e17-s2-missing-skill",
        ))

    with connect() as conn:
        conn.execute("""INSERT INTO aip_eval_authority_revocation
            (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
             approval_ref,reason_hash)
            VALUES ('org-org','dev-project','e17-s2-revoked',%s,%s,%s,%s,%s)""",
            (target[0].identity_id, datetime.now(UTC), "isolated-test-owner",
             Jsonb({"testOnly": True}), "e" * 64))
        conn.commit()
    with pytest.raises(AipReleaseGateRejected):
        service.publish(scope, actor="isolated-test-actor", request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash="f" * 64, idempotency_key="e17-s2-publish",
        ))
    with pytest.raises(AipReleaseGateRejected):
        service.derive_gate(scope, actor="isolated-test-actor", request=request.model_copy(
            update={"idempotency_key": "e17-s2-after-revocation"},
        ))
    with connect(scope) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM aip_publication_event
            WHERE org_id=%s AND project_id=%s""", scope.key).fetchone()["n"] == 0
