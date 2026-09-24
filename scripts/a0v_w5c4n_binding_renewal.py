#!/usr/bin/env python3
"""Append twelve schedule bindings to current rev2 controls, once."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
from aos_api.pipeline_schedule_control_owner import decode_binding
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c4f_successor_bindings as prior
import a0v_w5c4h_disabled_definition as definition
import a0v_w5c4m_control_renewal as controls

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4n-binding-renewal")


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
        raise ValueError("W5C4N_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _key(pipeline):
    prefix = pipeline.split("-", 1)[0].lower()
    if prefix not in {f"p{i:02d}" for i in range(1, 13)}:
        raise ValueError("W5C4N_CANONICAL_PIPELINE_REQUIRED")
    return f"a0v-w5c4n-binding-{prefix}-20260924-v1"


def preflight():
    if (controls.audit()["outcome"] != "W5C4M_TWELVE_CONTROL_REV2_GREEN"
            or definition.audit()["outcome"] != "W5C4H_DISABLED_DEFINITION_GREEN"):
        raise ValueError("W5C4N_CONTROL_OR_DEFINITION_DRIFT")
    old = {m["pipelineId"]: m for m in prior._load("wave-result")["members"]}
    new_controls = {m["pipelineId"]: m["ref"] for m in
                    controls._load("wave-result")["members"]}
    material = controls.selections._material()
    now = datetime.now(timezone.utc)
    runtime = enabled.observe()
    if (len(old) != 12 or len(new_controls) != 12
            or datetime.fromisoformat(material["expiresAt"]) <= now + timedelta(hours=2)
            or runtime["host"]["pid"] != material["hostPid"]
            or runtime["counts"]["business"] != material["businessCounts"]
            or runtime["counts"]["attempts"] != 0
            or runtime["counts"]["canary"] != 0
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4N_RUNTIME_OR_WINDOW_DRIFT")
    schedule_ids = [m["scheduleId"] for m in old.values()]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute("""SELECT DISTINCT ON (schedule_id) *
          FROM pipeline_schedule_control_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND schedule_id=ANY(%s)
          ORDER BY schedule_id,revision DESC""", (schedule_ids,)).fetchall()
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_schedule_control_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s
            AND idempotency_key=ANY(%s)) AS keys,
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member
            WHERE org_id='org-org' AND project_id='dev-project'
            AND schedule_id=ANY(%s)) AS occupied,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND id=ANY(%s) AND enabled) AS enabled""",
          (prepared.registered.INSTALLATION,
           [_key(m["pipelineId"]) for m in old.values()], schedule_ids, schedule_ids)).fetchone())
    latest = {row["pipeline_id"]: decode_binding(row) for row in rows}
    if len(latest) != 12 or state != {"keys": 0, "occupied": 12, "enabled": 0}:
        raise ValueError("W5C4N_BINDING_STATE_DRIFT")
    members = []
    for pipeline, item in old.items():
        saved = latest[pipeline]
        previous = saved.ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        if (saved.schedule_id != item["scheduleId"]
                or previous != item["ref"]
                or saved.installation_id != prepared.registered.INSTALLATION):
            raise ValueError("W5C4N_BINDING_PREDECESSOR_DRIFT")
        members.append({"pipelineId": pipeline, "scheduleId": item["scheduleId"],
                        "controlRef": new_controls[pipeline], "previousRef": previous})
    return {"outcome": "W5C4N_BINDING_PREFLIGHT_GREEN", "members": members,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def issue():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4N_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("wave-intent", {"hostPid": before["hostPid"],
           "businessCounts": before["businessCounts"], "resend": False})
    service = prepared._plane().pipeline_control_factory.build(
        TenantScope("org-org", "dev-project"))
    refs = []
    for item in sorted(before["members"], key=lambda m: m["pipelineId"]):
        pipeline = item["pipelineId"]
        _write("intent-" + pipeline, {**item, "idempotencyKey": _key(pipeline),
                                      "resend": False})
        ref = service.bind_schedule(pipeline_id=pipeline, schedule_id=item["scheduleId"],
            control_ref=item["controlRef"], actor=prepared.ACTOR,
            idempotency_key=_key(pipeline), previous_ref=item["previousRef"])
        value = ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        _write("result-" + pipeline, {"pipelineId": pipeline,
                "scheduleId": item["scheduleId"], "ref": value})
        refs.append({"pipelineId": pipeline, "scheduleId": item["scheduleId"],
                     "ref": value})
    _write("wave-result", {"members": refs})
    return {"outcome": "W5C4N_BINDINGS_ACCEPTED", "members": len(refs)}


def audit():
    intent, result = _load("wave-intent"), _load("wave-result")
    runtime = enabled.observe()
    expected = {m["scheduleId"]: m for m in result["members"]}
    schedule_ids = list(expected)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute("""SELECT * FROM pipeline_schedule_control_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND generation=%s ORDER BY schedule_id,revision""",
          (prepared.registered.INSTALLATION, prepared.registered.GENERATION)).fetchall()
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member
            WHERE org_id='org-org' AND project_id='dev-project'
            AND schedule_id=ANY(%s)) AS occupied,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND id=ANY(%s) AND enabled) AS enabled""",
            (schedule_ids, schedule_ids)).fetchone())
    if len(rows) != 24 or len(expected) != 12:
        raise ValueError("W5C4N_BINDING_COUNT_DRIFT")
    for row in rows:
        if row["idempotency_key"] != _key(row["pipeline_id"]):
            continue
        saved = decode_binding(row)
        item = expected.get(saved.schedule_id)
        previous = _load("intent-" + saved.pipeline_id)["previousRef"]
        if (item is None or row["idempotency_key"] != _key(saved.pipeline_id)
                or saved.ref.model_dump(mode="json", by_alias=True,
                                        exclude_none=True) != item["ref"]
                or saved.control_ref.model_dump(mode="json", by_alias=True,
                                                exclude_none=True)
                   != _load("intent-" + saved.pipeline_id)["controlRef"]
                or str(row["binding_id"]) != previous["resourceId"].removeprefix(
                    "schedule-control-")
                or row["revision"] != previous["revision"] + 1
                or row["previous_hash"] != previous["contentHash"]):
            raise ValueError("W5C4N_BINDING_AUTHORITY_DRIFT")
    if (state != {"occupied": 12, "enabled": 0}
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]
            or definition.audit()["outcome"] != "W5C4H_DISABLED_DEFINITION_GREEN"):
        raise ValueError("W5C4N_BINDING_POST_GATE_DRIFT")
    return {"outcome": "W5C4N_TWELVE_BINDING_RENEWALS_GREEN",
            "bindingRows": 24, "currentMembers": 12, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "issue", "audit"))
    value = globals()[parser.parse_args().phase]()
    if value.get("outcome") == "W5C4N_BINDING_PREFLIGHT_GREEN":
        value = {**value, "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
