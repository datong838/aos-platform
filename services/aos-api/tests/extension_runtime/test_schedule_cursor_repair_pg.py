"""Exact repair authority for a stale schedule execution cursor."""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
from psycopg import sql
import pytest

from test_ecommerce_growth_cutover_pg import _migration
from test_lifecycle_pg import database, pytestmark


@pytest.fixture
def cursor_db(database):
    conn, _, schema = database
    created_maintainer = conn.execute(
        "SELECT 1 FROM pg_roles WHERE rolname='aos_extension_maintainer'"
    ).fetchone() is None
    if created_maintainer:
        conn.execute("CREATE ROLE aos_extension_maintainer NOSUPERUSER NOBYPASSRLS NOLOGIN")
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_extension_maintainer").format(
        sql.Identifier(schema)
    ))
    conn.execute("""CREATE TABLE meta_schedule(
      org_id text NOT NULL,project_id text NOT NULL,id text NOT NULL,enabled boolean NOT NULL,
      last_run jsonb,updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,id))""")
    conn.execute("""CREATE TABLE meta_schedule_run(
      org_id text NOT NULL,project_id text NOT NULL,id text NOT NULL,schedule_id text NOT NULL,
      scheduled_for timestamptz NOT NULL,trigger text NOT NULL,status text NOT NULL,
      started_at timestamptz,finished_at timestamptz,duration_ms bigint,rows_written bigint,
      error_code text,executor_stopped boolean NOT NULL DEFAULT false,
      PRIMARY KEY(org_id,project_id,id))""")
    _migration(Path(__file__).resolve().parents[2], "a0v_077_schedule_cursor_repair.py",
               conn, schema=schema)
    old = {"id": "run-old", "status": "succeeded", "trigger": "manual"}
    conn.execute(
        "INSERT INTO meta_schedule VALUES('org-org','dev-project','schedule',false,%s::jsonb,NOW())",
        (json.dumps(old),),
    )
    conn.execute("""INSERT INTO meta_schedule_run(org_id,project_id,id,schedule_id,scheduled_for,
      trigger,status,started_at,finished_at,duration_ms,rows_written,error_code,executor_stopped)
      VALUES
      ('org-org','dev-project','run-old','schedule',NOW()-interval '2 hour','manual','succeeded',
       NOW()-interval '2 hour',NOW()-interval '119 minute',1000,60,'',true),
      ('org-org','dev-project','run-current','schedule',NOW()-interval '1 hour','cron','succeeded',
       NOW()-interval '1 hour',NOW()-interval '59 minute',2000,65,'',true)""")
    try:
        yield conn, schema, old
    finally:
        if created_maintainer:
            conn.execute("DROP OWNED BY aos_extension_maintainer")
            conn.execute("DROP ROLE aos_extension_maintainer")


def _request(**changes):
    value = {
        "schemaVersion": "aos.schedule-cursor-repair/v1",
        "orgId": "org-org",
        "projectId": "dev-project",
        "scheduleId": "schedule",
        "expectedCurrentRunId": "run-old",
        "targetRunId": "run-current",
        "idempotencyKey": "repair-once",
    }
    value.update(changes)
    return value


def _repair(conn, schema, request):
    return conn.execute(
        sql.SQL("SELECT {}.schedule_cursor_repair_a0v_077(%s::jsonb,%s) AS body").format(
            sql.Identifier(schema)
        ),
        (json.dumps(request), "fixture-operator"),
    ).fetchone()[0]


def test_exact_repair_is_atomic_immutable_and_replayable(cursor_db):
    conn, schema, old = cursor_db
    first = _repair(conn, schema, _request())
    replay = _repair(conn, schema, _request())
    row = conn.execute("SELECT last_run FROM meta_schedule WHERE id='schedule'").fetchone()[0]
    assert first["replayed"] is False and replay["replayed"] is True
    assert replay["receiptId"] == first["receiptId"]
    assert first["priorLastRun"] == old
    assert row == first["repairedLastRun"]
    assert row["id"] == "run-current" and row["rowsWritten"] == 65
    assert conn.execute("SELECT count(*) FROM schedule_cursor_repair_receipt").fetchone()[0] == 1
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        conn.execute("DELETE FROM schedule_cursor_repair_receipt")


@pytest.mark.parametrize("fault", ["expected", "older", "running", "tenant"])
def test_repair_rejects_non_authoritative_target(cursor_db, fault):
    conn, schema, old = cursor_db
    request = _request()
    if fault == "expected":
        request["expectedCurrentRunId"] = "different"
    elif fault == "older":
        request["targetRunId"] = "run-old"
    elif fault == "running":
        conn.execute("""INSERT INTO meta_schedule_run(org_id,project_id,id,schedule_id,scheduled_for,
          trigger,status,executor_stopped) VALUES('org-org','dev-project','running','schedule',NOW(),
          'cron','running',false)""")
    else:
        request["orgId"] = "dev-org"
    with pytest.raises(psycopg.Error):
        _repair(conn, schema, request)
    assert conn.execute("SELECT last_run FROM meta_schedule WHERE id='schedule'").fetchone()[0] == old
    assert conn.execute("SELECT count(*) FROM schedule_cursor_repair_receipt").fetchone()[0] == 0
