"""Isolated PostgreSQL proof of the first durable feedback target and receipt."""

import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.ecommerce_growth_daily_review_target import BoundDailyReviewTarget, DailyReviewFeedbackWorker
from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort,
    EcommerceGrowthFeedbackConflict,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1", reason="dedicated PostgreSQL opt-in required"
)
PG = {
    "host": os.getenv("AOS_EXTENSION_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("AOS_EXTENSION_PG_PORT", "18432")),
    "user": os.getenv("AOS_EXTENSION_PG_USER", "postgres"),
    "dbname": os.getenv("AOS_EXTENSION_PG_DATABASE", "postgres"),
}
ROOT = Path(__file__).resolve().parents[2]
SCOPE = TenantScope("org-org", "dev-project")


def ref(kind, identity):
    return {"resourceType": kind, "resourceId": identity, "revision": 1,
            "contentHash": "sha256:" + "a" * 64, "receiptId": identity}


@pytest.fixture
def database():
    dbname = "a1_daily_review_" + uuid4().hex[:16]
    host_role = "a1_feedback_" + uuid4().hex[:14]
    admin = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_role = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    created_maintainer = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_extension_maintainer'").fetchone() is None
    if created_role:
        admin.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    if created_maintainer:
        admin.execute("CREATE ROLE aos_extension_maintainer NOSUPERUSER NOBYPASSRLS NOLOGIN")
    password = os.getenv("AOS_EXTENSION_PG_PASSWORD") or os.getenv("PGPASSWORD")
    assert password, "dedicated test PostgreSQL password required"
    admin.execute(sql.SQL("CREATE ROLE {} NOSUPERUSER NOBYPASSRLS NOINHERIT LOGIN PASSWORD {}").format(
        sql.Identifier(host_role), sql.Literal(password)))
    admin.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(host_role)))
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    options = {**PG, "dbname": dbname}
    owner = psycopg.connect(**options, autocommit=True, row_factory=dict_row)
    try:
        owner.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        owner.execute("""CREATE TABLE extension_runtime_binding(
          org_id text,project_id text,installation_id uuid,generation uuid,
          execution_epoch bigint,revision bigint,desired_state text,observed_state text,
          enabled boolean,operation_fence boolean,
          PRIMARY KEY(org_id,project_id,installation_id,generation))""")
        owner.execute("""CREATE TABLE extension_operation_dispatch_binding(
          org_id text,project_id text,operation_id text,handler_kind text,operation_fence boolean,
          revision bigint,installation_id uuid,generation uuid,execution_epoch bigint,
          cutover_group_id uuid,cutover_group_revision bigint,
          PRIMARY KEY(org_id,project_id,operation_id))""")
        owner.execute("""CREATE TABLE ecommerce_growth_runtime_command_receipt(
          org_id text,project_id text,operation_id text,target_receipt_ref jsonb,response jsonb,
          dispatch_revision bigint,installation_id uuid,generation uuid,execution_epoch bigint,
          cutover_group_id uuid,cutover_group_revision bigint,runtime_revision bigint,
          request_hash text)""")
        for filename in (
            "ar2_004_ecommerce_growth_feedback.py",
            "a0v_028_dispatch_read_lock.py",
            "a0v_099_ecommerce_daily_review_target.py",
        ):
            spec = importlib.util.spec_from_file_location(filename, ROOT / "alembic/versions" / filename)
            migration = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(migration)
            migration.op = SimpleNamespace(execute=owner.execute)
            migration.upgrade()
        owner.execute("GRANT USAGE ON SCHEMA public TO aos_runtime")
        owner.execute("GRANT SELECT,UPDATE ON extension_runtime_binding TO aos_runtime")
        owner.execute("GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime")
        yield SimpleNamespace(owner=owner, options=options, host_role=host_role)
    finally:
        owner.close()
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(host_role)))
        if created_role:
            admin.execute("DROP ROLE aos_runtime")
        if created_maintainer:
            admin.execute("DROP ROLE aos_extension_maintainer")
        admin.close()


def seed(database, *, claimed=True):
    owner = database.owner
    installation, generation, group, lease = uuid4(), uuid4(), uuid4(), uuid4()
    review, artifact, task, brief = (
        ref("ContentReviewReceipt", "review-1"), ref("ArtifactRevision", "artifact-1"),
        ref("Task", "task-1"), ref("TaskBriefRevision", "brief-1"),
    )
    payload = {"sequence": 1, "kind": "daily_review", "targetId": "daily_review-1",
               "businessTitle": "今日内容复盘", "businessSummary": "内容通过评审，效果待观察。",
               "targetPhase": None}
    command_id = "feedback-1"
    owner.execute("""INSERT INTO extension_runtime_binding VALUES(%s,%s,%s,%s,3,6,'enabled','ready',true,false)""",
                  (*SCOPE.key, installation, generation))
    operations = (
        "ecommerce_growth_investigation_describe", "ecommerce_growth_case_put",
        "ecommerce_growth_schedule_put", "ecommerce_growth_schedule_trigger",
        "ecommerce_growth_data_fulfill", "ecommerce_growth_analysis_advance",
        "ecommerce_growth_review_advance", "ecommerce_growth_content_generate",
        "ecommerce_growth_content_review",
    )
    for operation in operations:
        owner.execute("""INSERT INTO extension_operation_dispatch_binding VALUES(
          %s,%s,%s,'extension',false,5,%s,%s,3,%s,11)""",
                      (*SCOPE.key, operation, installation, generation, group))
    response = {"receiptRef": review, "decision": "ACCEPT", "artifactRef": artifact,
                "taskRef": task, "briefRef": brief}
    owner.execute("""INSERT INTO ecommerce_growth_runtime_command_receipt VALUES(
      %s,%s,'ecommerce_growth_content_review',%s,%s,5,%s,%s,3,%s,11,6,%s)""",
                  (*SCOPE.key, psycopg.types.json.Jsonb(review), psycopg.types.json.Jsonb(response),
                   installation, generation, group, "sha256:" + "c" * 64))
    owner.execute("""INSERT INTO ecommerce_growth_feedback_command VALUES(
      %s,%s,%s,%s,'ACCEPT',%s,%s,%s,%s,'reviewer',%s)""",
                  (*SCOPE.key, command_id, "sha256:" + "b" * 64,
                   *(psycopg.types.json.Jsonb(item) for item in (review, artifact, task, brief)), datetime.now(UTC)))
    owner.execute("""INSERT INTO ecommerce_growth_feedback_segment(
      org_id,project_id,command_id,sequence,kind,target_id,payload,state,attempt,
      lease_token,lease_expires_at,updated_at)
      VALUES(%s,%s,%s,1,'daily_review','daily_review-1',%s,%s,%s,%s,%s,%s)""",
                  (*SCOPE.key, command_id, psycopg.types.json.Jsonb(payload),
                   "claimed" if claimed else "pending", 1 if claimed else 0,
                   lease if claimed else None,
                   datetime.now(UTC) + timedelta(minutes=5) if claimed else None,
                   datetime.now(UTC)))
    for sequence, kind in ((2, "improvement_observation"), (3, "memory_candidate")):
        other = {"sequence": sequence, "kind": kind, "targetId": f"{kind}-1",
                 "businessTitle": "待后续处理", "businessSummary": "等待真实数据与治理。", "targetPhase": None}
        owner.execute("""INSERT INTO ecommerce_growth_feedback_segment(
          org_id,project_id,command_id,sequence,kind,target_id,payload,state,updated_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,'pending',%s)""",
                      (*SCOPE.key, command_id, sequence, kind, other["targetId"],
                       psycopg.types.json.Jsonb(other), datetime.now(UTC)))
    owner.execute("""INSERT INTO ecommerce_growth_feedback_checkpoint VALUES(%s,%s,%s,0,1,%s)""",
                  (*SCOPE.key, command_id, datetime.now(UTC)))
    return SimpleNamespace(
        installation=installation, generation=generation, group=group, lease=lease,
        review=review, artifact=artifact, task=task, brief=brief, payload=payload,
        command_id=command_id,
    )


def runtime_connection(database, scope=SCOPE):
    conn = psycopg.connect(**{**database.options, "user": database.host_role},
                           autocommit=False, row_factory=dict_row)
    conn.execute("SET ROLE aos_runtime")
    conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
    conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
    return conn


def target_args(item):
    return {
        "command_id": item.command_id,
        "command": {"decision": "ACCEPT", "reviewReceiptRef": item.review,
                    "artifactRef": item.artifact, "taskRef": item.task, "briefRef": item.brief},
        "claim": {"sequence": 1, "kind": "daily_review", "targetId": "daily_review-1",
                  "payload": item.payload, "leaseToken": str(item.lease), "checkpointVersion": 1},
        "origin": {"reviewReceiptRef": item.review},
    }


def test_current_target_receipt_ack_and_tenant_isolation(database):
    item = seed(database)
    with runtime_connection(database) as conn:
        target = BoundDailyReviewTarget(HostTransaction(conn), SCOPE)
        receipt = target.put(**target_args(item))
        assert target.put(**target_args(item)) == receipt
        assert target.read_receipt(target_id="daily_review-1", expected_receipt=receipt) == receipt
        port = BoundEcommerceGrowthFeedbackPort(
            HostTransaction(conn), SCOPE, actor="worker", checked_at=datetime.now(UTC),
            target_receipt_readers={
                "daily_review": target.read_receipt,
                "improvement_observation": lambda **_: None,
                "memory_candidate": lambda **_: None,
                "content_return_target": lambda **_: None,
            },
        )
        checkpoint = port.acknowledge(
            command_id=item.command_id,
            claim={**target_args(item)["claim"], "attempt": 1},
            target_receipt_ref=receipt,
        )
        assert checkpoint["completedSequence"] == 1
    with runtime_connection(database) as conn:
        target = BoundDailyReviewTarget(HostTransaction(conn), SCOPE)
        assert target.read_receipt(target_id="daily_review-1", expected_receipt=receipt) == receipt
        assert conn.execute("SELECT count(*) AS n FROM ecommerce_growth_daily_review_target").fetchone()["n"] == 1
    with runtime_connection(database, TenantScope("dev-org", "dev-project")) as conn:
        assert conn.execute("SELECT count(*) AS n FROM ecommerce_growth_daily_review_target").fetchone()["n"] == 0


@pytest.mark.parametrize("drift", ["epoch", "disabled", "lease", "payload"])
def test_drift_rejected_without_target_row(database, drift):
    item = seed(database)
    if drift == "epoch":
        database.owner.execute("UPDATE extension_operation_dispatch_binding SET execution_epoch=4")
    elif drift == "disabled":
        database.owner.execute("UPDATE extension_runtime_binding SET enabled=false,operation_fence=true")
    elif drift == "lease":
        database.owner.execute("UPDATE ecommerce_growth_feedback_segment SET lease_token=%s WHERE sequence=1", (uuid4(),))
    else:
        database.owner.execute("UPDATE ecommerce_growth_feedback_segment SET payload=jsonb_set(payload,'{businessSummary}','\"漂移\"'::jsonb)")
    with runtime_connection(database) as conn:
        target = BoundDailyReviewTarget(HostTransaction(conn), SCOPE)
        with pytest.raises(EcommerceGrowthFeedbackConflict):
            target.put(**target_args(item))
        conn.rollback()
    assert database.owner.execute("SELECT count(*) AS n FROM ecommerce_growth_daily_review_target").fetchone()["n"] == 0


def test_uncommitted_target_does_not_survive_failed_ack(database):
    item = seed(database)
    conn = runtime_connection(database)
    try:
        target = BoundDailyReviewTarget(HostTransaction(conn), SCOPE)
        target.put(**target_args(item))
        conn.rollback()
    finally:
        conn.close()
    assert database.owner.execute("SELECT count(*) AS n FROM ecommerce_growth_daily_review_target").fetchone()["n"] == 0


def test_full_current_worker_claim_target_and_ack(database):
    seed(database, claimed=False)
    worker = DailyReviewFeedbackWorker(connect=lambda scope: runtime_connection(database, scope))
    result = worker.run_one(SCOPE, "feedback-1")
    assert result["status"] == "DAILY_REVIEW_ACKED"
    assert worker.run_one(SCOPE, "feedback-1")["status"] == "ALREADY_ACKED"
    row = database.owner.execute("""SELECT state,attempt,target_receipt_ref FROM ecommerce_growth_feedback_segment
      WHERE org_id=%s AND project_id=%s AND command_id='feedback-1' AND sequence=1""", SCOPE.key).fetchone()
    assert row["state"] == "acked" and row["attempt"] == 1
    assert row["target_receipt_ref"] == result["receiptRef"]
    assert database.owner.execute("SELECT count(*) AS n FROM ecommerce_growth_daily_review_target").fetchone()["n"] == 1
