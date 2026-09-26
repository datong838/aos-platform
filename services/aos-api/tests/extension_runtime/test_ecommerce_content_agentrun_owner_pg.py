"""Isolated PG proof of the accepted Run to single AgentRun claim boundary."""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from test_ecommerce_content_taskrun_owner_pg import (
    CANARY, ROOT, SCOPE, database, ref, runtime_connection, seed,
)


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1", reason="dedicated PostgreSQL opt-in required"
)


@pytest.fixture
def agent_database(database):
    owner = database.owner
    owner.execute("ALTER TABLE aip_task ADD COLUMN current_plan_revision_id text")
    owner.execute("""CREATE TABLE aip_agent_run(
      org_id text,project_id text,agent_run_id text,task_id text,task_run_id text,status text)""")
    owner.execute("""CREATE TABLE aip_agent_registry_receipt(
      org_id text,project_id text,operation text,idempotency_key text,
      result_ref jsonb,status text)""")
    owner.execute("""CREATE TABLE aip_model_capacity_reservation(
      org_id text,project_id text,reservation_id text,agent_run_id text,
      status text,expires_at timestamptz)""")
    filename = "a0v_102_ecommerce_content_agentrun_intent.py"
    spec = importlib.util.spec_from_file_location(filename, ROOT / "alembic/versions" / filename)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=owner.execute)
    migration.upgrade()
    filename = "a0v_103_ecommerce_content_capacity_intent.py"
    spec = importlib.util.spec_from_file_location(filename, ROOT / "alembic/versions" / filename)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=owner.execute)
    migration.upgrade()
    yield database


def accepted_taskrun(database, *, put_inline=False):
    seed(database)
    owner = database.owner
    owner.execute("INSERT INTO aip_task VALUES(%s,%s,'task-1','executing','plan-1')", SCOPE.key)
    owner.execute("""INSERT INTO aip_plan_revision VALUES(
      %s,%s,'plan-1','task-1','review-key-1:content-run:plan',%s,'approved')""",
                  (*SCOPE.key, Jsonb({"reviewReceiptRef": ref("ReviewDecisionReceipt", "review-1")})))
    owner.execute("""INSERT INTO aip_task_run VALUES(
      %s,%s,'run-1','plan-1','task-1','review-key-1:content-run:run','running')""", SCOPE.key)
    token = uuid4()
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_intent_put_a0v_101(%s) AS ok",
                            ("review-key-1",)).fetchone()["ok"] is True
        conn.commit()
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s) AS ok",
                            ("review-key-1", token)).fetchone()["ok"] is True
        conn.commit()
    with runtime_connection(database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_taskrun_ack_a0v_101(%s,%s,%s,%s) AS ok",
                            ("review-key-1", token, "plan-1", "run-1")).fetchone()["ok"] is True
        if put_inline:
            assert conn.execute("SELECT public.ecommerce_growth_content_agentrun_put_a0v_102(%s) AS ok",
                                ("review-key-1",)).fetchone()["ok"] is True
        conn.commit()


def test_next_intent_put_claim_once_and_tenant_zero_canary(agent_database):
    accepted_taskrun(agent_database, put_inline=True)
    token = uuid4()
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_agentrun_claim_a0v_102(%s,%s) AS ok",
                            ("review-key-1", token)).fetchone()["ok"] is True
        conn.commit()
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_agentrun_claim_a0v_102(%s,%s) AS ok",
                            ("review-key-1", uuid4())).fetchone()["ok"] is False
        row = conn.execute("SELECT state,attempt,claim_token FROM public.ecommerce_growth_content_agentrun_intent").fetchone()
        assert (row["state"], row["attempt"], row["claim_token"]) == ("claimed", 1, token)
    with runtime_connection(agent_database, CANARY) as conn:
        assert conn.execute("SELECT count(*) AS n FROM public.ecommerce_growth_content_agentrun_intent").fetchone()["n"] == 0


def test_ack_requires_original_agent_owner_receipt_and_fences_epoch(agent_database):
    accepted_taskrun(agent_database, put_inline=True)
    token = uuid4()
    with runtime_connection(agent_database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_agentrun_claim_a0v_102(%s,%s)", ("review-key-1", token))
        conn.commit()
    owner = agent_database.owner
    owner.execute("INSERT INTO aip_agent_run VALUES(%s,%s,'agent-1','task-1','run-1','queued')", SCOPE.key)
    with runtime_connection(agent_database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_agentrun_ack_a0v_102(%s,%s,%s)",
                         ("review-key-1", token, "agent-1"))
        conn.rollback()
    owner.execute("""INSERT INTO aip_agent_registry_receipt VALUES(
      %s,%s,'agent_run.create','review-key-1',%s,'applied')""",
                  (*SCOPE.key, Jsonb({"resourceId": "agent-1"})))
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_agentrun_ack_a0v_102(%s,%s,%s) AS ok",
                            ("review-key-1", token, "agent-1")).fetchone()["ok"] is True
        conn.commit()
    assert owner.execute("SELECT state,agent_run_id FROM ecommerce_growth_content_agentrun_intent").fetchone() == {
        "state": "accepted", "agent_run_id": "agent-1"
    }
    owner.execute("UPDATE extension_runtime_binding SET execution_epoch=4")
    with runtime_connection(agent_database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_agentrun_put_a0v_102(%s)",
                         ("review-key-1",))
        conn.rollback()


def test_committed_old_taskrun_cannot_be_backfilled(agent_database):
    accepted_taskrun(agent_database)
    with runtime_connection(agent_database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_agentrun_put_a0v_102(%s)",
                         ("review-key-1",))
        conn.rollback()
    assert agent_database.owner.execute(
        "SELECT count(*) AS n FROM ecommerce_growth_content_agentrun_intent"
    ).fetchone()["n"] == 0


def test_capacity_intent_must_follow_agentrun_ack_in_same_transaction(agent_database):
    accepted_taskrun(agent_database, put_inline=True)
    token = uuid4()
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_agentrun_claim_a0v_102(%s,%s) AS ok",
                            ("review-key-1", token)).fetchone()["ok"] is True
        conn.commit()
    owner = agent_database.owner
    owner.execute("INSERT INTO aip_agent_run VALUES(%s,%s,'agent-1','task-1','run-1','queued')", SCOPE.key)
    owner.execute("""INSERT INTO aip_agent_registry_receipt VALUES(
      %s,%s,'agent_run.create','review-key-1',%s,'applied')""",
                  (*SCOPE.key, Jsonb({"resourceId": "agent-1"})))
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_agentrun_ack_a0v_102(%s,%s,%s) AS ok",
                            ("review-key-1", token, "agent-1")).fetchone()["ok"] is True
        assert conn.execute("SELECT public.ecommerce_growth_content_capacity_put_a0v_103(%s) AS ok",
                            ("review-key-1",)).fetchone()["ok"] is True
        conn.commit()
    with runtime_connection(agent_database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_capacity_put_a0v_103(%s)",
                         ("review-key-1",))
        conn.rollback()
    with runtime_connection(agent_database, CANARY) as conn:
        assert conn.execute("SELECT count(*) AS n FROM ecommerce_growth_content_capacity_intent").fetchone()["n"] == 0


def test_capacity_ack_requires_running_and_live_reservation(agent_database):
    accepted_taskrun(agent_database, put_inline=True)
    token = uuid4()
    with runtime_connection(agent_database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_agentrun_claim_a0v_102(%s,%s)",
                     ("review-key-1", token))
        conn.commit()
    owner = agent_database.owner
    owner.execute("INSERT INTO aip_agent_run VALUES(%s,%s,'agent-1','task-1','run-1','queued')", SCOPE.key)
    owner.execute("""INSERT INTO aip_agent_registry_receipt VALUES(
      %s,%s,'agent_run.create','review-key-1',%s,'applied')""",
                  (*SCOPE.key, Jsonb({"resourceId": "agent-1"})))
    with runtime_connection(agent_database) as conn:
        conn.execute("SELECT public.ecommerce_growth_content_agentrun_ack_a0v_102(%s,%s,%s)",
                     ("review-key-1", token, "agent-1"))
        conn.execute("SELECT public.ecommerce_growth_content_capacity_put_a0v_103(%s)",
                     ("review-key-1",))
        conn.commit()
    claim = uuid4()
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_capacity_claim_a0v_103(%s,%s) AS ok",
                            ("review-key-1", claim)).fetchone()["ok"] is True
        conn.commit()
    with runtime_connection(agent_database) as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT public.ecommerce_growth_content_capacity_ack_a0v_103(%s,%s,%s)",
                         ("review-key-1", claim, "cap-1"))
        conn.rollback()
    owner.execute("UPDATE aip_agent_run SET status='running' WHERE agent_run_id='agent-1'")
    owner.execute("""INSERT INTO aip_model_capacity_reservation VALUES(
      %s,%s,'cap-1','agent-1','reserved',now()+interval '5 minutes')""", SCOPE.key)
    with runtime_connection(agent_database) as conn:
        assert conn.execute("SELECT public.ecommerce_growth_content_capacity_ack_a0v_103(%s,%s,%s) AS ok",
                            ("review-key-1", claim, "cap-1")).fetchone()["ok"] is True
        conn.commit()
    assert owner.execute("SELECT state,capacity_reservation_id FROM ecommerce_growth_content_capacity_intent").fetchone() == {
        "state": "accepted", "capacity_reservation_id": "cap-1"
    }
