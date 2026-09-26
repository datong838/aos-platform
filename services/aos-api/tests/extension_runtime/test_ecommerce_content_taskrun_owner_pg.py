"""Isolated database proof of one-attempt content Run handoff intent."""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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
CANARY = TenantScope("dev-org", "dev-project")


def ref(kind, identity, fill="a"):
    return {"resourceType": kind, "resourceId": identity, "revision": 1,
            "contentHash": "sha256:" + fill * 64}


@pytest.fixture
def database():
    dbname = "a1_content_run_" + uuid4().hex[:16]
    host_role = "a1_content_" + uuid4().hex[:14]
    admin = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        admin.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    password = os.getenv("AOS_EXTENSION_PG_PASSWORD") or os.getenv("PGPASSWORD")
    assert password, "dedicated test PostgreSQL password required"
    admin.execute(sql.SQL("CREATE ROLE {} NOSUPERUSER NOBYPASSRLS NOINHERIT LOGIN PASSWORD {}").format(
        sql.Identifier(host_role), sql.Literal(password)))
    admin.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(host_role)))
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    options = {**PG, "dbname": dbname}
    owner = psycopg.connect(**options, autocommit=True, row_factory=dict_row)
    try:
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
          org_id text,project_id text,operation_id text,idempotency_key text,
          target_receipt_ref jsonb,response jsonb,dispatch_revision bigint,
          installation_id uuid,generation uuid,execution_epoch bigint,
          cutover_group_id uuid,cutover_group_revision bigint,runtime_revision bigint,
          request_hash text)""")
        owner.execute("""CREATE TABLE aip_task_brief_revision(
          org_id text,project_id text,brief_id text,revision integer,task_id text,
          schema_ref jsonb,spec jsonb,content_hash text)""")
        owner.execute("""CREATE TABLE aip_task(
          org_id text,project_id text,task_id text,status text,
          PRIMARY KEY(org_id,project_id,task_id))""")
        owner.execute("""CREATE TABLE aip_plan_revision(
          org_id text,project_id text,plan_revision_id text,task_id text,
          idempotency_key text,risk jsonb,approval_status text,
          PRIMARY KEY(org_id,project_id,plan_revision_id))""")
        owner.execute("""CREATE TABLE aip_task_run(
          org_id text,project_id text,run_id text,plan_revision_id text,task_id text,
          idempotency_key text,status text,
          PRIMARY KEY(org_id,project_id,run_id))""")
        filename = "a0v_101_ecommerce_content_taskrun_intent.py"
        spec = importlib.util.spec_from_file_location(filename, ROOT / "alembic/versions" / filename)
        migration = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)
        migration.op = SimpleNamespace(execute=owner.execute)
        migration.upgrade()
        owner.execute("GRANT USAGE ON SCHEMA public TO aos_runtime")
        owner.execute("GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime")
        yield SimpleNamespace(owner=owner, options=options, host_role=host_role)
    finally:
        owner.close()
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(host_role)))
        if created_runtime:
            admin.execute("DROP ROLE aos_runtime")
        admin.close()


def runtime_connection(database, scope=SCOPE):
    conn = psycopg.connect(**{**database.options, "user": database.host_role},
                           autocommit=False, row_factory=dict_row)
    conn.execute("SET ROLE aos_runtime")
    conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
    conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
    return conn


def seed(database):
    owner = database.owner
    installation, generation, group = uuid4(), uuid4(), uuid4()
    review, task, brief, plan = (
        ref("ReviewDecisionReceipt", "review-1"), ref("Task", "task-1"),
        ref("TaskBriefRevision", "brief-1"), ref("GrowthPlanRevision", "plan-1"),
    )
    owner.execute("""INSERT INTO extension_runtime_binding VALUES(
      %s,%s,%s,%s,3,6,'enabled','ready',true,false)""",
                  (*SCOPE.key, installation, generation))
    owner.execute("""INSERT INTO extension_operation_dispatch_binding VALUES(
      %s,%s,'ecommerce_growth_review_advance','extension',false,5,%s,%s,3,%s,11)""",
                  (*SCOPE.key, installation, generation, group))
    owner.execute("""INSERT INTO aip_task_brief_revision VALUES(
      %s,%s,'brief-1',1,'task-1',%s,%s,%s)""",
                  (*SCOPE.key, Jsonb({"resourceId": "schema://aos/ecommerce/content-campaign-brief/v2"}),
                   Jsonb({"taskRef": task, "growthPlanRef": plan}), "a" * 64))
    response = {"receiptRef": review, "decision": "ACCEPT", "requestHash": "sha256:" + "b" * 64,
                "taskRef": task, "briefRef": brief, "growthPlanRef": plan,
                "sideEffects": {"taskRunCreatedCount": 0}}
    owner.execute("""INSERT INTO ecommerce_growth_runtime_command_receipt VALUES(
      %s,%s,'ecommerce_growth_review_advance','review-key-1',%s,%s,5,%s,%s,3,%s,11,6,%s)""",
                  (*SCOPE.key, Jsonb(review), Jsonb(response), installation, generation, group,
                   response["requestHash"]))
    return SimpleNamespace(installation=installation, review=review)


def test_intent_put_claim_once_and_current_epoch_fence(database):
    seed(database)
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_intent_put_a0v_101(%s) AS value",
                            ("review-key-1",)).fetchone()["value"] is True
        conn.commit()
    token = uuid4()
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s) AS value",
                            ("review-key-1", token)).fetchone()["value"] is True
        conn.commit()
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s) AS value",
                            ("review-key-1", uuid4())).fetchone()["value"] is False
        row = conn.execute("SELECT state,attempt,claim_token FROM public.ecommerce_growth_content_taskrun_intent").fetchone()
        assert (row["state"], row["attempt"], row["claim_token"]) == ("claimed", 1, token)
    database.owner.execute("UPDATE extension_runtime_binding SET execution_epoch=4")
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s) AS value",
                            ("review-key-1", uuid4())).fetchone()["value"] is False


def test_claimed_intent_needs_running_same_task_before_ack(database):
    seed(database)
    token = uuid4()
    with runtime_connection(database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_taskrun_intent_put_a0v_101(%s)", ("review-key-1",))
        conn.commit()
    with runtime_connection(database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s)", ("review-key-1", token))
        conn.commit()
    with runtime_connection(database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_taskrun_ack_a0v_101(%s,%s,%s,%s)",
                         ("review-key-1", token, "plan-1", "run-1"))
        conn.rollback()
    owner = database.owner
    owner.execute("INSERT INTO aip_task VALUES(%s,%s,'task-1','executing')", SCOPE.key)
    owner.execute("""INSERT INTO aip_plan_revision VALUES(
      %s,%s,'plan-1','task-1','review-key-1:content-run:plan',%s,'approved')""",
                  (*SCOPE.key, Jsonb({"reviewReceiptRef": ref("ReviewDecisionReceipt", "review-1")})))
    owner.execute("""INSERT INTO aip_task_run VALUES(
      %s,%s,'run-1','plan-1','task-1','review-key-1:content-run:run','running')""", SCOPE.key)
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_ack_a0v_101(%s,%s,%s,%s) AS value",
                            ("review-key-1", token, "plan-1", "run-1")).fetchone()["value"] is True
        conn.commit()
    with runtime_connection(database) as conn:
        row = conn.execute("SELECT state,attempt,run_id FROM public.ecommerce_growth_content_taskrun_intent").fetchone()
        assert (row["state"], row["attempt"], row["run_id"]) == ("accepted", 1, "run-1")
    with runtime_connection(database, CANARY) as conn:
        assert conn.execute("SELECT count(*) AS n FROM public.ecommerce_growth_content_taskrun_intent").fetchone()["n"] == 0


def test_runtime_cannot_edit_intent_or_ack_unrelated_run(database):
    seed(database)
    token = uuid4()
    with runtime_connection(database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_taskrun_intent_put_a0v_101(%s)", ("review-key-1",))
        conn.commit()
    with runtime_connection(database) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE public.ecommerce_growth_content_taskrun_intent SET state='accepted'")
        conn.rollback()
    with runtime_connection(database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s)", ("review-key-1", token))
        conn.commit()
    owner = database.owner
    owner.execute("INSERT INTO aip_task VALUES(%s,%s,'task-1','executing')", SCOPE.key)
    owner.execute("""INSERT INTO aip_plan_revision VALUES(
      %s,%s,'plan-1','task-1','another-review:content-run:plan',%s,'approved')""",
                  (*SCOPE.key, Jsonb({"reviewReceiptRef": ref("ReviewDecisionReceipt", "review-1")})))
    owner.execute("""INSERT INTO aip_task_run VALUES(
      %s,%s,'run-1','plan-1','task-1','review-key-1:content-run:run','running')""", SCOPE.key)
    with runtime_connection(database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_taskrun_ack_a0v_101(%s,%s,%s,%s)",
                         ("review-key-1", token, "plan-1", "run-1"))
        conn.rollback()
    assert owner.execute("SELECT state FROM public.ecommerce_growth_content_taskrun_intent").fetchone()["state"] == "claimed"
