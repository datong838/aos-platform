#!/usr/bin/env python3
"""Disable one failed natural definition through its Owner; never rerun work."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4q_natural_enable as prior


ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260925-w5c4s-failed-definition-disable")
KEY = "a0v-w5c4s-disable-after-natural-failure-20260925-v1"
DEFINITION = prior.definition.prior.DEFINITION
HASH = "sha256:d80287ce2e70e034060c6e056f8e93f3d8c9654b4beccd3bc386e095eda15227"
GROUP = "081cd331-cdf8-5bdc-891e-e3b82baa77c7"
ATTEMPT = "a5e60b0d-2d97-44d0-88bf-9f08990624d1"
WORKER_PID = 37241


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _load(name):
    path = STATE / (name + ".json")
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C4S_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _gate(value):
    try:
        head = value["head"]
        claim, attempt, runs, facts = (value[key] for key in
                                       ("claims", "attempts", "runs", "facts"))
        return (head == {"revision": 3, "state": "enabled", "content_hash": HASH}
                and len(claim) == 1 and claim[0]["group_id"] == GROUP
                and claim[0]["trigger"] == "cron"
                and claim[0]["scheduled_for"] == "2026-09-24 20:00:00+00:00"
                and len(attempt) == 1 and attempt[0]["attempt_id"] == ATTEMPT
                and attempt[0]["state"] == "failed"
                and attempt[0]["operation_kind"] == "recoverable_store"
                and attempt[0]["terminal_reason_code"] == "RECOVERABLE_EXECUTION_EXCEPTION"
                and attempt[0]["terminal_error_type"] == "PermissionError"
                and runs == [{"status": "running", "executor_stopped": False,
                              "finished_at": None, "n": 12}]
                and facts == {"members": 12, "enabled": 12, "receipts": 26,
                              "links": 0, "pending": 0, "canary": 0, "key_count": 0}
                and value["member_revisions"] == [{"revision": 3, "n": 12}]
                and value["key_revisions"] == []
                and value["host_alive"] is False
                and value["worker_pid"] == WORKER_PID)
    except (KeyError, TypeError, ValueError):
        return False


def _read():
    host_pid = prior._load("intent")["hostPid"]
    worker = prior._worker()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""", (DEFINITION,)).fetchone()
        claims = [dict(row) for row in conn.execute("""SELECT group_id::text,trigger,
          scheduled_for FROM pipeline_snapshot_schedule_claim WHERE org_id='org-org'
          AND project_id='dev-project' AND request->'definitionRef'->>'resourceId'=%s
          ORDER BY created_at""", ("snapshot-schedule-" + DEFINITION,)).fetchall()]
        attempts = [dict(row) for row in conn.execute("""SELECT attempt_id::text,state,
          operation_kind,terminal_reason_code,terminal_error_type FROM
          extension_runtime_execution_attempt WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s AND generation=%s
          ORDER BY accepted_at""", (prior.prepared.registered.INSTALLATION,
                                       prior.prepared.registered.GENERATION)).fetchall()]
        runs = [dict(row) for row in conn.execute("""SELECT r.status,r.executor_stopped,
          r.finished_at,count(*) AS n FROM pipeline_snapshot_schedule_member m
          JOIN meta_schedule_run r ON (r.org_id,r.project_id,r.id)=
            (m.org_id,m.project_id,m.run_id) WHERE m.org_id='org-org'
          AND m.project_id='dev-project' AND m.group_id=%s
          GROUP BY r.status,r.executor_stopped,r.finished_at""", (GROUP,)).fetchall()]
        member_revisions = [dict(row) for row in conn.execute("""SELECT revision,
          count(*) AS n FROM pipeline_snapshot_schedule_current_member WHERE
          org_id='org-org' AND project_id='dev-project' AND definition_id=%s
          GROUP BY revision""", (DEFINITION,)).fetchall()]
        key_revisions = [dict(row) for row in conn.execute("""SELECT revision,
          content_hash,previous_hash FROM pipeline_snapshot_schedule_definition_revision
          WHERE org_id='org-org' AND project_id='dev-project' AND definition_id=%s
          AND idempotency_key=%s""", (DEFINITION, KEY)).fetchall()]
        facts = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member WHERE
            org_id='org-org' AND project_id='dev-project' AND definition_id=%s) AS members,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org' AND
            project_id='dev-project' AND enabled AND pipeline_id IN
              (SELECT DISTINCT pipeline_id FROM pipeline_source_selection_revision
               WHERE org_id='org-org' AND project_id='dev-project'
               AND installation_id=%s)) AS enabled,
          (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id='org-org'
            AND workspace_id='dev-project') AS receipts,
          (SELECT count(*) FROM ecom_link WHERE org_id='org-org'
            AND workspace_id='dev-project' AND deleted_at IS NULL) AS links,
          (SELECT count(*) FROM projection_outbox WHERE org_id='org-org'
            AND workspace_id='dev-project' AND projected IS FALSE) AS pending,
          (SELECT count(*) FROM extension_runtime_binding WHERE org_id='dev-org'
            AND project_id='dev-project') AS canary,
          (SELECT count(*) FROM pipeline_snapshot_schedule_definition_revision WHERE
            org_id='org-org' AND project_id='dev-project' AND definition_id=%s
            AND idempotency_key=%s) AS key_count""",
          (DEFINITION, prior.prepared.registered.INSTALLATION, DEFINITION, KEY)).fetchone())
    for claim in claims:
        claim["scheduled_for"] = str(claim["scheduled_for"])
    return {"head": dict(head) if head else None, "claims": claims,
            "attempts": attempts, "runs": runs, "facts": facts,
            "member_revisions": member_revisions, "key_revisions": key_revisions,
            "host_alive": _alive(host_pid), "worker_pid": worker["pid"]}


def _service():
    from aos_api.tenant_scope import TenantScope
    return prior.prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=False)


def preflight():
    value = _read()
    if not _gate(value):
        raise ValueError("W5C4S_FAIL_CLOSED_GATE_DRIFT")
    current = _service().read(definition_id=DEFINITION, actor=prior.prepared.ACTOR)
    expected = {"resourceType": "SnapshotScheduleDefinitionRevision",
                "resourceId": "snapshot-schedule-" + DEFINITION,
                "revision": 3, "contentHash": HASH}
    if current["ref"] != expected:
        raise ValueError("W5C4S_CURRENT_PERMISSION_OR_REF_DRIFT")
    return {"outcome": "W5C4S_DISABLE_PREFLIGHT_GREEN", "expectedRef": expected,
            "idempotencyKey": KEY, "actor": prior.prepared.ACTOR,
            "groupId": GROUP, "attemptId": ATTEMPT, "facts": value["facts"]}


def disable():
    if STATE.exists():
        raise ValueError("W5C4S_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    result = _service().transition(definition_id=DEFINITION,
        actor=prior.prepared.ACTOR, intent="disable",
        expected_ref=before["expectedRef"], idempotency_key=KEY)
    _write("result", result)
    return {"outcome": "W5C4S_DISABLE_ACCEPTED", "ref": result["ref"],
            "state": result["body"]["state"]}


def audit():
    intent, result = _load("intent"), _load("result")
    value = _read()
    facts = value["facts"]
    expected = {"members": 12, "enabled": 0, "receipts": 26,
                "links": 0, "pending": 0, "canary": 0, "key_count": 1}
    if (value["head"] != {"revision": 4, "state": "disabled",
                          "content_hash": result["ref"]["contentHash"]}
            or facts != expected or len(value["claims"]) != 1
            or len(value["attempts"]) != 1
            or value["runs"] != [{"status": "running", "executor_stopped": False,
                                  "finished_at": None, "n": 12}]
            or value["member_revisions"] != [{"revision": 4, "n": 12}]
            or value["key_revisions"] != [{"revision": 4,
                 "content_hash": result["ref"]["contentHash"],
                 "previous_hash": HASH}]
            or result["body"]["state"] != "disabled"
            or intent["expectedRef"]["contentHash"] != HASH
            or value["host_alive"] is not False):
        raise ValueError("W5C4S_DISABLE_AUDIT_DRIFT")
    return {"outcome": "W5C4S_DEFINITION_DISABLED_GREEN", "ref": result["ref"],
            "schedulesEnabled": 0, "retired": False, "originalRunsRunning": 12}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "disable", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
