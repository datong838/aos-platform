#!/usr/bin/env python3
"""Read-only 50-second natural attempt observation; never dispatches work."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c4q_natural_enable as prior

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4r-natural-observation")
DEFINITION = prior.definition.prior.DEFINITION
INSTALLATION = prior.prepared.registered.INSTALLATION
GENERATION = prior.prepared.registered.GENERATION
GROUP = prior.prepared.registered.GROUP


def _worker():
    if not prior.WORKER_STATUS.is_file():
        raise ValueError("W5C4R_WORKER_STATUS_MISSING")
    value = json.loads(prior.WORKER_STATUS.read_text())
    observed = datetime.fromisoformat(value["observedAt"])
    if (value.get("workerState") not in {"IDLE", "RUNNING"}
            or value.get("workerTaskAlive") is not True
            or value.get("workerError") is not None
            or value.get("hostInThisProcess") is not False
            or value.get("topology") != "independent"
            or value.get("pid") != prior._listener(18181)
            or datetime.now(timezone.utc) - observed > timedelta(seconds=10)):
        raise ValueError("W5C4R_INDEPENDENT_WORKER_DRIFT")
    return value


def _save(value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / "samples.jsonl"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        output.flush()
        os.fsync(output.fileno())


def sample():
    intent = prior._load("intent")
    now = datetime.now(timezone.utc)
    worker = _worker()
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""", (DEFINITION,)).fetchone()
        claims = [dict(row) for row in conn.execute("""SELECT group_id::text,scheduled_for,
          trigger,created_at FROM pipeline_snapshot_schedule_claim
          WHERE org_id='org-org' AND project_id='dev-project'
          AND request->'definitionRef'->>'resourceId'=%s ORDER BY created_at""",
          ("snapshot-schedule-" + DEFINITION,)).fetchall()]
        attempts = [dict(row) for row in conn.execute("""SELECT attempt_id::text,state,
          revision,operation_kind,terminal_reason_code,terminal_error_type,
          accepted_at,heartbeat_at,completed_at FROM extension_runtime_execution_attempt
          WHERE org_id='org-org' AND project_id='dev-project'
          AND installation_id=%s AND generation=%s ORDER BY accepted_at""",
          (INSTALLATION, GENERATION)).fetchall()]
        run_rows = [dict(row) for row in conn.execute("""SELECT
          m.group_id::text,r.status,r.executor_stopped,r.finished_at,
          count(*) AS n FROM pipeline_snapshot_schedule_member m
          JOIN meta_schedule_run r ON (r.org_id,r.project_id,r.id)=
            (m.org_id,m.project_id,m.run_id)
          WHERE m.org_id='org-org' AND m.project_id='dev-project'
          AND m.group_id=ANY(%s::uuid[])
          GROUP BY m.group_id,r.status,r.executor_stopped,r.finished_at""",
          ([c["group_id"] for c in claims],)).fetchall()]
        facts = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_group_id=%s AND installation_id=%s AND generation=%s
            AND handler_kind='extension' AND operation_fence IS FALSE) AS routes,
          (SELECT count(*) FROM extension_dispatch_claim_gate WHERE org_id='org-org'
            AND project_id='dev-project' AND cutover_group_id=%s
            AND claim_paused IS FALSE) AS unpaused_gate,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND enabled AND pipeline_id IN
              (SELECT DISTINCT pipeline_id FROM pipeline_source_selection_revision
               WHERE org_id='org-org' AND project_id='dev-project'
               AND installation_id=%s)) AS schedules_enabled,
          (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id='org-org'
            AND workspace_id='dev-project') AS store_receipts,
          (SELECT count(*) FROM ecom_link WHERE org_id='org-org'
            AND workspace_id='dev-project' AND deleted_at IS NULL) AS live_links,
          (SELECT count(*) FROM projection_outbox WHERE org_id='org-org'
            AND workspace_id='dev-project' AND projected IS FALSE) AS projection_pending,
          (SELECT count(*) FROM extension_runtime_binding WHERE org_id='dev-org'
            AND project_id='dev-project') AS canary""",
          (GROUP, INSTALLATION, GENERATION, GROUP, INSTALLATION)).fetchone())
    value = {"observedAt": now.isoformat(), "workerPid": worker["pid"],
        "workerState": worker["workerState"], "workerTaskAlive": worker["workerTaskAlive"],
        "hostPid": runtime["host"]["pid"], "resourcesHeld": enabled.configured._held(
            runtime["resources"]), "businessCounts": runtime["counts"]["business"],
        "definition": dict(head) if head else None, "claims": claims,
        "attempts": attempts, "runGroups": run_rows, "facts": facts}
    if (head is None or head["revision"] != 3 or head["state"] != "enabled"
            or head["content_hash"] != prior._load("result")["ref"]["contentHash"]
            or worker["pid"] != intent["workerPid"]
            or runtime["host"]["pid"] != intent["hostPid"]
            or not value["resourcesHeld"] or len(claims) > 1 or len(attempts) > 1
            or facts["routes"] != 9 or facts["unpaused_gate"] != 1
            or facts["schedules_enabled"] != 12 or facts["canary"] != 0):
        value["observation"] = "FROZEN_AUTHORITY_DRIFT"
    elif attempts and attempts[0]["state"] in {"succeeded", "failed", "abandoned"}:
        value["observation"] = "ATTEMPT_FORMAL_TERMINAL"
    else:
        value["observation"] = "WAITING_FOR_NATURAL_TERMINAL"
    _save(value)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("sample", "loop"))
    phase = parser.parse_args().phase
    while True:
        try:
            value = sample()
        except Exception as exc:
            value = {"observedAt": datetime.now(timezone.utc).isoformat(),
                     "observation": "FROZEN_OBSERVER_ERROR",
                     "errorType": type(exc).__name__}
            _save(value)
            print(json.dumps(value), flush=True)
            return
        print(json.dumps({"observedAt": value["observedAt"],
            "observation": value["observation"], "claims": len(value["claims"]),
            "attempts": [{"id": a["attempt_id"], "state": a["state"],
                          "revision": a["revision"],
                          "reason": a["terminal_reason_code"]}
                         for a in value["attempts"]]}, ensure_ascii=False), flush=True)
        if phase == "sample" or value["observation"] != "WAITING_FOR_NATURAL_TERMINAL":
            return
        time.sleep(50)


if __name__ == "__main__":
    main()
