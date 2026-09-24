#!/usr/bin/env python3
"""Reconfigure one disabled definition to twelve current renewed bindings."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c4h_disabled_definition as prior
import a0v_w5c4n_binding_renewal as bindings

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4o-disabled-definition-renewal")
KEY = "a0v-w5c4o-disabled-definition-renewal-20260924-v1"


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
        raise ValueError("W5C4O_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    from aos_api.tenant_scope import TenantScope
    if bindings.audit()["outcome"] != "W5C4N_TWELVE_BINDING_RENEWALS_GREEN":
        raise ValueError("W5C4O_BINDING_DRIFT")
    old = prior._load("result")
    if (old["ref"]["revision"] != 1 or old["body"]["state"] != "disabled"
            or old["body"]["cron"] != prior.CRON):
        raise ValueError("W5C4O_PRIOR_DEFINITION_DRIFT")
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)
    result = service.options(actor=prepared.ACTOR,
        installation_id=prepared.registered.INSTALLATION,
        generation=prepared.registered.GENERATION)
    new = {m["scheduleId"]: m for m in bindings._load("wave-result")["members"]}
    if (result.get("status") != "ready" or len(result.get("members", [])) != 12
            or result.get("policies") != [old["body"]["policyRef"]]
            or len(new) != 12):
        raise ValueError("W5C4O_OPTIONS_NOT_EXACT")
    for item in result["members"]:
        match = new.get(item["scheduleId"])
        if (match is None or item["pipelineId"] != match["pipelineId"]
                or item["bindingRef"] != match["ref"]
                or item["definitionId"] != prior.DEFINITION):
            raise ValueError("W5C4O_MEMBER_OPTION_DRIFT")
    runtime = enabled.observe()
    material = bindings.controls.selections._material()
    now = datetime.now(timezone.utc)
    if (datetime.fromisoformat(material["expiresAt"]) <= now + timedelta(hours=2)
            or runtime["host"]["pid"] != material["hostPid"]
            or runtime["counts"]["business"] != material["businessCounts"]
            or runtime["counts"]["attempts"] != 0
            or runtime["counts"]["canary"] != 0
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4O_RUNTIME_OR_WINDOW_DRIFT")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""",
          (prior.DEFINITION,)).fetchone()
        keys = conn.execute("""SELECT count(*) AS n FROM
          pipeline_snapshot_schedule_definition_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s AND idempotency_key=%s""",
          (prior.DEFINITION, KEY)).fetchone()["n"]
    if (head is None or head["revision"] != 1 or head["state"] != "disabled"
            or head["content_hash"] != old["ref"]["contentHash"] or keys):
        raise ValueError("W5C4O_HEAD_OR_KEY_DRIFT")
    return {"outcome": "W5C4O_CONFIGURE_PREFLIGHT_GREEN",
            "definitionId": prior.DEFINITION, "cron": prior.CRON,
            "policyRef": old["body"]["policyRef"], "expectedRef": old["ref"],
            "members": [{"scheduleId": m["scheduleId"], "bindingRef": m["bindingRef"]}
                        for m in result["members"]],
            "idempotencyKey": KEY, "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def configure():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4O_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)
    result = service.configure(definition_id=prior.DEFINITION, actor=prepared.ACTOR,
        cron=prior.CRON, policy_ref=before["policyRef"], members=before["members"],
        expected_ref=before["expectedRef"], idempotency_key=KEY)
    _write("result", result)
    return {"outcome": "W5C4O_CONFIGURE_ACCEPTED", "ref": result["ref"],
            "state": result["body"]["state"]}


def audit():
    intent, result = _load("intent"), _load("result")
    runtime = enabled.observe()
    schedule_ids = [m["scheduleId"] for m in intent["members"]]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""",
          (prior.DEFINITION,)).fetchone()
        row = conn.execute("""SELECT content_hash,previous_hash,idempotency_key,body
          FROM pipeline_snapshot_schedule_definition_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s AND revision=2""",
          (prior.DEFINITION,)).fetchone()
        current = conn.execute("""SELECT schedule_id,revision FROM
          pipeline_snapshot_schedule_current_member WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""",
          (prior.DEFINITION,)).fetchall()
        enabled_count = conn.execute("""SELECT count(*) AS n FROM meta_schedule
          WHERE org_id='org-org' AND project_id='dev-project'
          AND id=ANY(%s) AND enabled""", (schedule_ids,)).fetchone()["n"]
    expected = {m["scheduleId"]: m["bindingRef"] for m in intent["members"]}
    observed = {m["scheduleId"]: m["bindingRef"] for m in result["body"]["members"]}
    if (head is None or row is None or head["revision"] != 2
            or head["state"] != "disabled" or row["content_hash"] != head["content_hash"]
            or row["previous_hash"] != intent["expectedRef"]["contentHash"]
            or row["idempotency_key"] != KEY
            or result["ref"]["contentHash"] != head["content_hash"]
            or result["body"]["state"] != "disabled"
            or result["body"]["policyRef"] != intent["policyRef"]
            or result["body"]["cron"] != intent["cron"]
            or observed != expected
            or {m["schedule_id"] for m in current} != set(schedule_ids)
            or any(m["revision"] != 2 for m in current)
            or enabled_count != 0
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C4O_CONFIGURE_AUDIT_DRIFT")
    return {"outcome": "W5C4O_DISABLED_DEFINITION_REV2_GREEN",
            "revision": 2, "state": "disabled", "members": 12,
            "schedulesEnabled": 0, "contentHash": head["content_hash"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "configure", "audit"))
    value = globals()[parser.parse_args().phase]()
    if value.get("outcome") == "W5C4O_CONFIGURE_PREFLIGHT_GREEN":
        value = {**value, "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
