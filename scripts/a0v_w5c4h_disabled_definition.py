#!/usr/bin/env python3
"""Configure one third-successor snapshot definition, disabled by Owner."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c4f_successor_bindings as bindings
import a0v_w5c4g_definition_options as options

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4h-disabled-definition")
DEFINITION = "38c5d08c-ee40-4167-b129-8f95276e0c7a"
KEY = "a0v-w5c4h-third-successor-definition-configure-20260924-v1"
CRON = "0 4 * * *"


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
        raise ValueError("W5C4H_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    if bindings.audit()["outcome"] != "W5C4F_TWELVE_BINDINGS_GREEN":
        raise ValueError("W5C4H_BINDINGS_DRIFT")
    saved = json.loads((options.STATE / "options.json").read_text())
    if not saved["accepted"] or len(saved["options"]["policies"]) != 1:
        raise ValueError("W5C4H_OFFICIAL_OPTIONS_NOT_FROZEN")
    result = saved["options"]
    expected = {m["scheduleId"]: m for m in bindings._load("wave-result")["members"]}
    if (result["status"] != "ready" or len(result["members"]) != 12
            or any(expected.get(m["scheduleId"], {}).get("ref") != m["bindingRef"]
                   for m in result["members"])):
        raise ValueError("W5C4H_BINDING_OPTION_DRIFT")
    now = datetime.now(timezone.utc)
    control_window = json.loads((ROOT.parent / ".aos-recovery-20260920/state/"
        "q-advisor-baseline/20260924-w5c4c-controls-preflight/material.json").read_text())
    if any(datetime.fromisoformat(m["draft"]["expiresAt"].replace("Z", "+00:00"))
           <= now for m in control_window["members"]):
        raise ValueError("W5C4H_CONTROL_WINDOW_EXPIRED")
    runtime = enabled.observe()
    if (runtime["host"]["pid"] != saved["hostPid"]
            or runtime["counts"]["business"] != saved["businessCounts"]
            or runtime["counts"]["canary"] != 0
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4H_RUNTIME_DRIFT")
    schedule_ids = list(expected)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        existing = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_definition_head
            WHERE org_id='org-org' AND project_id='dev-project' AND definition_id=%s) AS head,
          (SELECT count(*) FROM pipeline_snapshot_schedule_definition_revision
            WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s) AS key_count,
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member
            WHERE org_id='org-org' AND project_id='dev-project'
            AND schedule_id=ANY(%s)) AS occupied,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND id=ANY(%s) AND enabled) AS enabled""",
            (DEFINITION, KEY, schedule_ids, schedule_ids)).fetchone())
    if existing != {"head": 0, "key_count": 0, "occupied": 0, "enabled": 0}:
        raise ValueError("W5C4H_DEFINITION_ALREADY_EXISTS_OR_SCHEDULE_DRIFT")
    return {"outcome": "W5C4H_CONFIGURE_PREFLIGHT_GREEN", "definitionId": DEFINITION,
        "cron": CRON, "policyRef": result["policies"][0],
        "members": [{"scheduleId": m["scheduleId"], "bindingRef": m["bindingRef"]}
                    for m in result["members"]], "actor": prepared.ACTOR,
        "idempotencyKey": KEY, "expectedRef": None,
        "hostPid": runtime["host"]["pid"],
        "businessCounts": runtime["counts"]["business"]}


def configure():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4H_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)
    result = service.configure(definition_id=DEFINITION, actor=prepared.ACTOR,
        cron=CRON, policy_ref=before["policyRef"], members=before["members"],
        expected_ref=None, idempotency_key=KEY)
    _write("result", result)
    return {"outcome": "W5C4H_CONFIGURE_ACCEPTED", "ref": result["ref"],
            "state": result["body"]["state"]}


def audit():
    intent, result = _load("intent"), _load("result")
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""", (DEFINITION,)).fetchone()
        revision = conn.execute("""SELECT request,request_hash,content_hash,body,
          idempotency_key FROM pipeline_snapshot_schedule_definition_revision
          WHERE org_id='org-org' AND project_id='dev-project' AND definition_id=%s
          AND revision=1""", (DEFINITION,)).fetchone()
        members = conn.execute("""SELECT schedule_id FROM pipeline_snapshot_schedule_current_member
          WHERE org_id='org-org' AND project_id='dev-project' AND definition_id=%s""",
          (DEFINITION,)).fetchall()
        enabled_count = conn.execute("""SELECT count(*) AS n FROM meta_schedule
          WHERE org_id='org-org' AND project_id='dev-project' AND id=ANY(%s) AND enabled""",
          ([m["scheduleId"] for m in intent["members"]],)).fetchone()["n"]
    if (head is None or revision is None or head["revision"] != 1
            or head["state"] != "disabled" or revision["content_hash"] != head["content_hash"]
            or revision["idempotency_key"] != KEY
            or result["ref"]["contentHash"] != head["content_hash"]
            or result["body"]["state"] != "disabled"
            or result["body"]["policyRef"] != intent["policyRef"]
            or {m["scheduleId"]: m["bindingRef"] for m in result["body"]["members"]}
               != {m["scheduleId"]: m["bindingRef"] for m in intent["members"]}
            or {str(m["schedule_id"]) for m in members}
               != {m["scheduleId"] for m in intent["members"]}
            or enabled_count != 0
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C4H_CONFIGURE_AUDIT_DRIFT")
    return {"outcome": "W5C4H_DISABLED_DEFINITION_GREEN", "revision": 1,
            "state": "disabled", "members": 12, "schedulesEnabled": 0,
            "contentHash": head["content_hash"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "configure", "audit"))
    value = globals()[parser.parse_args().phase]()
    if value.get("outcome") == "W5C4H_CONFIGURE_PREFLIGHT_GREEN":
        value = {**value, "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
