#!/usr/bin/env python3
"""Enable one exact successor definition for its natural daily slot, once."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

from a0v_formal_text_model_renewal import database_connect
from aos_api.qyh_cron_scheduler import cron_matches
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c4o_disabled_definition_renewal as definition

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4q-natural-enable")
KEY = "a0v-w5c4q-third-successor-natural-enable-20260924-v1"
WORKER_STATUS = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
                 "20260924-w5c4p-snapshot-worker/status.json")


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
        raise ValueError("W5C4Q_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _listener(port):
    output = subprocess.check_output(["lsof", "-nP", f"-tiTCP:{port}",
                                      "-sTCP:LISTEN"], text=True)
    values = [int(line) for line in output.splitlines() if line.strip()]
    if len(values) != 1:
        raise ValueError("W5C4Q_LISTENER_NOT_UNIQUE")
    return values[0]


def _worker():
    if not WORKER_STATUS.is_file():
        raise ValueError("W5C4Q_WORKER_STATUS_MISSING")
    value = json.loads(WORKER_STATUS.read_text())
    observed = datetime.fromisoformat(value["observedAt"])
    if (value.get("workerState") != "IDLE" or value.get("workerTaskAlive") is not True
            or value.get("workerError") is not None
            or value.get("hostInThisProcess") is not False
            or value.get("topology") != "independent"
            or value.get("pid") != _listener(18181)
            or datetime.now(timezone.utc) - observed > timedelta(seconds=10)):
        raise ValueError("W5C4Q_INDEPENDENT_WORKER_DRIFT")
    return value


def _next_slot(body, now):
    slot = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(48 * 60):
        if cron_matches(body["cron"], slot.astimezone(ZoneInfo(body["timezone"]))):
            return slot
        slot += timedelta(minutes=1)
    raise ValueError("W5C4Q_NEXT_SLOT_UNAVAILABLE")


def preflight():
    from aos_api.tenant_scope import TenantScope
    if (definition.audit()["outcome"] != "W5C4O_DISABLED_DEFINITION_REV2_GREEN"
            or resumed.audit()["outcome"] != "W5C3X_RESUME_GREEN"):
        raise ValueError("W5C4Q_AUTHORITY_DRIFT")
    worker = _worker()
    api_pid = _listener(8080)
    runtime = enabled.observe()
    if (runtime["host"]["pid"] != definition._load("intent")["hostPid"]
            or runtime["counts"]["business"] != definition._load("intent")["businessCounts"]
            or runtime["counts"]["attempts"] != 0
            or runtime["counts"]["canary"] != 0
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4Q_RUNTIME_DRIFT")
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)
    current = service.read(definition_id=definition.prior.DEFINITION, actor=prepared.ACTOR)
    expected = definition._load("result")
    if current != expected or current["ref"]["revision"] != 2:
        raise ValueError("W5C4Q_DEFINITION_REF_DRIFT")
    options = service.options(actor=prepared.ACTOR,
        installation_id=prepared.registered.INSTALLATION,
        generation=prepared.registered.GENERATION)
    members = {m["scheduleId"]: m["bindingRef"] for m in options.get("members", [])}
    if (options.get("status") != "ready" or len(members) != 12
            or options.get("policies") != [current["body"]["policyRef"]]
            or members != {m["scheduleId"]: m["bindingRef"]
                           for m in current["body"]["members"]}
            or any(m["definitionId"] != definition.prior.DEFINITION
                   for m in options["members"])):
        raise ValueError("W5C4Q_OFFICIAL_OPTIONS_DRIFT")
    now = datetime.now(timezone.utc)
    slot = _next_slot(current["body"], now)
    material = definition.bindings.controls.selections._material()
    control_end = datetime.fromisoformat(material["expiresAt"])
    control_start = datetime.fromisoformat(material["notBefore"])
    schedule_ids = list(members)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        budget = conn.execute("""SELECT r.revision,r.effective_from,r.effective_until
          FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r
          ON (r.org_id,r.project_id,r.policy_id,r.revision)=
             (h.org_id,h.project_id,h.policy_id,h.current_revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project'
          AND h.policy_id='a0v-ecommerce-budget-policy-v1'""").fetchone()
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_definition_revision
            WHERE org_id='org-org' AND project_id='dev-project'
            AND definition_id=%s AND idempotency_key=%s) AS key_count,
          (SELECT count(*) FROM meta_schedule_run WHERE org_id='org-org'
            AND project_id='dev-project' AND schedule_id=ANY(%s)
            AND (status='running' OR executor_stopped IS NOT TRUE)) AS unresolved_runs,
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND state='running') AS running_attempts,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved_dispatches,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND id=ANY(%s) AND enabled) AS enabled""",
          (definition.prior.DEFINITION, KEY, schedule_ids, schedule_ids)).fetchone())
    if (budget is None or budget["revision"] != 13
            or not budget["effective_from"] <= now < slot
            or not control_start <= now < slot
            or budget["effective_until"] <= slot + timedelta(seconds=1800)
            or control_end <= slot + timedelta(seconds=1800)
            or state != {"key_count": 0, "unresolved_runs": 0,
                         "running_attempts": 0, "unresolved_dispatches": 0,
                         "enabled": 0}):
        raise ValueError("W5C4Q_SLOT_OR_PENDING_GATE_DRIFT")
    return {"outcome": "W5C4Q_NATURAL_ENABLE_PREFLIGHT_GREEN",
            "definitionId": definition.prior.DEFINITION,
            "expectedRef": current["ref"], "nextSlotUtc": slot.isoformat(),
            "controlEndUtc": control_end.isoformat(),
            "budgetEndUtc": budget["effective_until"].isoformat(),
            "workerPid": worker["pid"], "apiPid": api_pid,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"],
            "idempotencyKey": KEY}


def enable():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4Q_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)
    result = service.transition(definition_id=before["definitionId"],
        actor=prepared.ACTOR, intent="enable",
        expected_ref=before["expectedRef"], idempotency_key=KEY)
    _write("result", result)
    return {"outcome": "W5C4Q_NATURAL_ENABLE_ACCEPTED",
            "ref": result["ref"], "state": result["body"]["state"]}


def audit():
    intent, result = _load("intent"), _load("result")
    worker, runtime = _worker(), enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""",
          (intent["definitionId"],)).fetchone()
        row = conn.execute("""SELECT previous_hash,idempotency_key,content_hash
          FROM pipeline_snapshot_schedule_definition_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s AND revision=3""",
          (intent["definitionId"],)).fetchone()
        schedule_ids = [m["scheduleId"] for m in result["body"]["members"]]
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member
            WHERE org_id='org-org' AND project_id='dev-project' AND definition_id=%s
            AND revision=3) AS members,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND id=ANY(%s) AND enabled) AS enabled""",
          (intent["definitionId"], schedule_ids)).fetchone())
    if (head is None or row is None or head["revision"] != 3
            or head["state"] != "enabled" or row["content_hash"] != head["content_hash"]
            or row["previous_hash"] != intent["expectedRef"]["contentHash"]
            or row["idempotency_key"] != KEY
            or result["ref"]["contentHash"] != head["content_hash"]
            or result["body"]["state"] != "enabled"
            or state != {"members": 12, "enabled": 12}
            or worker["pid"] != intent["workerPid"]
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]
            or runtime["counts"]["canary"] != 0):
        raise ValueError("W5C4Q_NATURAL_ENABLE_AUDIT_DRIFT")
    return {"outcome": "W5C4Q_NATURAL_ENABLE_GREEN", "revision": 3,
            "state": "enabled", "members": 12, "schedulesEnabled": 12,
            "nextSlotUtc": intent["nextSlotUtc"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "enable", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
