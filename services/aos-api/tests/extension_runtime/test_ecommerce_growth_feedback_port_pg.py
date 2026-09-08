"""Dedicated PostgreSQL proof for AR2-7C result feedback recovery."""

import importlib.util
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated PostgreSQL opt-in required",
)
PG = {"host": "127.0.0.1", "port": 18432, "user": "postgres", "dbname": "postgres"}
ROOT = Path(__file__).resolve().parents[2]


def exact(kind: str, identity: str, fill: str = "a") -> dict[str, object]:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": "sha256:" + fill * 64,
        "receiptId": f"receipt-{identity}",
    }


def digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def feedback_plan(command_id: str = "feedback-1", decision: str = "ACCEPT"):
    kinds = (
        ("daily_review", "improvement_observation", "memory_candidate")
        if decision == "ACCEPT"
        else ("content_return_target",)
    )
    review_ref = exact("ContentReviewReceipt", f"review-{command_id}")
    segments = [
        {
            "sequence": index,
            "kind": kind,
            "targetId": f"{kind}-{command_id}",
            "businessTitle": "内容结果回流",
            "businessSummary": "内容结果已进入受控回流流程。",
            "targetPhase": "content_generation" if kind == "content_return_target" else None,
        }
        for index, kind in enumerate(kinds, start=1)
    ]
    canonical = {
        "decision": decision,
        "reviewReceiptRef": review_ref,
        "artifactRef": exact("ArtifactRevision", f"artifact-{command_id}"),
        "taskRef": exact("Task", f"task-{command_id}"),
        "briefRef": exact("TaskBriefRevision", f"brief-{command_id}"),
        "segments": segments,
    }
    return {
        "commandId": "feedback-" + digest({"reviewReceiptRef": review_ref, "decision": decision})[:40],
        "requestHash": "sha256:" + digest(canonical),
        "decision": decision,
        "reviewReceiptRef": canonical["reviewReceiptRef"],
        "artifactRef": canonical["artifactRef"],
        "taskRef": canonical["taskRef"],
        "briefRef": canonical["briefRef"],
        "segments": segments,
        "sideEffects": {
            "providerInvocationCount": 0,
            "externalPublicationCount": 0,
            "externalBusinessMutationCount": 0,
            "taskCreatedCount": 0,
            "budgetSettlementCount": 0,
        },
    }


@pytest.fixture
def database():
    dbname = "ar2_feedback_" + uuid4().hex[:20]
    admin = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        admin.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    database_pg = {**PG, "dbname": dbname}
    owner = psycopg.connect(**database_pg, autocommit=True, row_factory=dict_row)
    try:
        owner.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        spec = importlib.util.spec_from_file_location(
            "ar2_004_test", ROOT / "alembic/versions/ar2_004_ecommerce_growth_feedback.py"
        )
        migration = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)
        migration.op = SimpleNamespace(execute=owner.execute)
        migration.upgrade()
        owner.execute("GRANT USAGE ON SCHEMA public TO aos_runtime")
        yield SimpleNamespace(owner=owner, pg=database_pg, migration=migration)
    finally:
        owner.close()
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
            (dbname,),
        )
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        if created_runtime:
            admin.execute("DROP ROLE aos_runtime")
        admin.close()


@contextmanager
def bound(database, scope: TenantScope):
    conn = psycopg.connect(**database.pg, autocommit=False, row_factory=dict_row)
    try:
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
        readers = {
            kind: (lambda **kwargs: kwargs["expected_receipt"])
            for kind in ("daily_review", "improvement_observation", "memory_candidate", "content_return_target")
        }
        yield BoundEcommerceGrowthFeedbackPort(
            HostTransaction(conn), scope, actor="数字同事",
            checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            target_receipt_readers=readers,
        ), conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def enqueue(port, item):
    return port.enqueue(
        review_receipt={"receiptRef": item["reviewReceiptRef"]},
        feedback_plan=item,
    )


def test_accept_replay_ordered_ack_and_aggregate_receipt(database):
    scope = TenantScope("org-org", "dev-project")
    item = feedback_plan()
    with bound(database, scope) as (port, _):
        assert enqueue(port, item)["replayed"] is False
        assert enqueue(port, item)["replayed"] is True
        for sequence, kind in enumerate(("daily_review", "improvement_observation", "memory_candidate"), start=1):
            claim = port.claim(command_id=item["commandId"], worker="worker-1")
            assert (claim["sequence"], claim["kind"], claim["attempt"]) == (sequence, kind, 1)
            target = exact("TargetReceipt", f"target-{sequence}", fill=str(sequence))
            result = port.acknowledge(
                command_id=item["commandId"], claim=claim,
                target_receipt_ref=target,
            )
            assert result["completedSequence"] == sequence
        assert result["receiptRef"]["resourceType"] == "FeedbackReceipt"
        assert port.claim(command_id=item["commandId"], worker="worker-1") is None

    rows = database.owner.execute(
        "SELECT state,target_receipt_ref FROM ecommerce_growth_feedback_segment ORDER BY sequence"
    ).fetchall()
    assert [row["state"] for row in rows] == ["acked", "acked", "acked"]
    assert all(row["target_receipt_ref"] is not None for row in rows)
    assert database.owner.execute("SELECT count(*) n FROM ecommerce_growth_feedback_receipt").fetchone()["n"] == 1


def test_unknown_restart_only_reconciles_same_target(database):
    scope = TenantScope("org-org", "dev-project")
    item = feedback_plan("feedback-return", "RETURN")
    with bound(database, scope) as (port, _):
        enqueue(port, item)
        claim = port.claim(command_id=item["commandId"], worker="worker-1")
        port.mark_unknown(command_id=item["commandId"], claim=claim, reason_code="target_outcome_unknown")
        assert port.claim(command_id=item["commandId"], worker="worker-2") is None
    with bound(database, scope) as (restarted, _):
        claim = restarted.claim_reconciliation(command_id=item["commandId"])
        assert claim["attempt"] == 1
        target = exact("TaskStageTargetReceipt", "return-target", fill="d")
        result = restarted.reconcile(
            command_id=item["commandId"], claim=claim,
            target_receipt_ref=target,
        )
        assert result["receiptRef"]["resourceType"] == "FeedbackReceipt"
    row = database.owner.execute(
        "SELECT state,attempt,target_receipt_ref FROM ecommerce_growth_feedback_segment WHERE command_id=%s",
        (item["commandId"],),
    ).fetchone()
    assert row["state"] == "acked" and row["attempt"] == 1
    assert row["target_receipt_ref"]["resourceId"] == "return-target"


def test_tenant_isolation_content_drift_and_nonempty_downgrade_gate(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    item = feedback_plan("feedback-isolated", "RETURN")
    with bound(database, positive) as (port, conn):
        enqueue(port, item)
        assert conn.execute("SELECT count(*) n FROM ecommerce_growth_feedback_command").fetchone()["n"] == 1
    with bound(database, positive) as (_, conn):
        drift = dict(item)
        drift["artifactRef"] = exact("ArtifactRevision", "artifact-drift", fill="e")
        drift["requestHash"] = item["requestHash"]
        with pytest.raises(psycopg.Error, match="content drifted"):
            conn.execute(
                "SELECT * FROM ecommerce_growth_feedback_enqueue_ar2_004(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)",
                (
                    drift["commandId"], drift["requestHash"], drift["decision"], json.dumps(drift["reviewReceiptRef"]),
                    json.dumps(drift["artifactRef"]), json.dumps(drift["taskRef"]), json.dumps(drift["briefRef"]),
                    json.dumps(drift["segments"], ensure_ascii=False), "数字同事", datetime(2026, 9, 8, 12, tzinfo=UTC),
                ),
            ).fetchone()
    with bound(database, canary) as (_, conn):
        assert conn.execute("SELECT count(*) n FROM ecommerce_growth_feedback_command").fetchone()["n"] == 0
    with pytest.raises(psycopg.Error, match="AR2_004_DOWNGRADE_REQUIRES_EMPTY"):
        database.migration.downgrade()
