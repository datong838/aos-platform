#!/usr/bin/env python3
"""Bind twelve disabled schedule slots to current successor controls once."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4e_successor_controls as controls
import a0v_w5c4d_successor_selections as selections
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c4a_dr_definition_retire as retired
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4f-successor-bindings")
DS_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"


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
        raise ValueError("W5C4F_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _key(pipeline):
    index = pipeline.split("-", 1)[0].lower()
    if index not in {f"p{i:02d}" for i in range(1, 13)}:
        raise ValueError("W5C4F_CANONICAL_PIPELINE_REQUIRED")
    return f"a0v-w5c4f-binding-{index}-20260924-v1"


def preflight():
    from aos_api.pipeline_schedule_control_owner import decode_binding
    if controls.audit()["outcome"] != "W5C4E_TWELVE_CONTROLS_GREEN":
        raise ValueError("W5C4F_CONTROL_AUTHORITY_DRIFT")
    material = selections._material()
    control_refs = {item["pipelineId"]: item["ref"] for item in
                    controls._load("wave-result")["members"]}
    runtime = enabled.observe()
    now = datetime.now(timezone.utc)
    if (len(control_refs) != 12 or len(material["members"]) != 12
            or runtime["host"]["pid"] != resumed._load("intent")["hostPid"]
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4F_RUNTIME_OR_MATERIAL_DRIFT")
    for item in material["members"]:
        draft = item["draft"]
        if not (datetime.fromisoformat(draft["notBefore"].replace("Z", "+00:00"))
                <= now + timedelta(minutes=1)
                < datetime.fromisoformat(draft["expiresAt"].replace("Z", "+00:00"))
                - timedelta(hours=2)):
            raise ValueError("W5C4F_CONTROL_WINDOW_DRIFT")
    schedule_ids = [item["scheduleId"] for item in material["members"]]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        old_rows = conn.execute("""SELECT DISTINCT ON (schedule_id) *
          FROM pipeline_schedule_control_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND schedule_id=ANY(%s)
          ORDER BY schedule_id,revision DESC""", (schedule_ids,)).fetchall()
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_schedule_control_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS new_bindings,
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member
            WHERE org_id='org-org' AND project_id='dev-project'
            AND schedule_id=ANY(%s)) AS occupied,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND enabled AND id=ANY(%s)) AS enabled""",
            (prepared.registered.INSTALLATION, schedule_ids, schedule_ids)).fetchone())
    old = {row["schedule_id"]: decode_binding(row) for row in old_rows}
    if (len(old) != 12 or state != {"new_bindings": 0, "occupied": 0, "enabled": 0}
            or any(binding.installation_id != DS_ID for binding in old.values())):
        raise ValueError("W5C4F_PREDECESSOR_BINDING_DRIFT")
    members = []
    for item in material["members"]:
        pipeline, schedule_id = item["pipelineId"], item["scheduleId"]
        if old[schedule_id].pipeline_id != pipeline:
            raise ValueError("W5C4F_PIPELINE_SCHEDULE_MISMATCH")
        members.append({"pipelineId": pipeline, "scheduleId": schedule_id,
                        "controlRef": control_refs[pipeline],
                        "previousRef": old[schedule_id].ref.model_dump(
                            mode="json", by_alias=True, exclude_none=True)})
    return {"outcome": "W5C4F_BINDING_PREFLIGHT_GREEN", "members": members,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def issue():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4F_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("wave-intent", {"hostPid": before["hostPid"],
                            "businessCounts": before["businessCounts"],
                            "expectedMembers": 12, "resend": False})
    service = prepared._plane().pipeline_control_factory.build(
        TenantScope("org-org", "dev-project"))
    refs = []
    for item in before["members"]:
        pipeline, key = item["pipelineId"], _key(item["pipelineId"])
        _write("intent-" + pipeline, {**item, "idempotencyKey": key, "resend": False})
        ref = service.bind_schedule(pipeline_id=pipeline, schedule_id=item["scheduleId"],
            control_ref=item["controlRef"], actor=prepared.ACTOR,
            idempotency_key=key, previous_ref=item["previousRef"])
        value = ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        _write("result-" + pipeline, {"pipelineId": pipeline, "ref": value})
        refs.append({"pipelineId": pipeline, "scheduleId": item["scheduleId"],
                     "ref": value})
    _write("wave-result", {"members": refs})
    return {"outcome": "W5C4F_BINDINGS_ACCEPTED", "members": len(refs)}


def audit():
    from aos_api.pipeline_schedule_control_owner import decode_binding
    material = selections._material()
    control_refs = {item["pipelineId"]: item["ref"] for item in
                    controls._load("wave-result")["members"]}
    intent, result = _load("wave-intent"), _load("wave-result")
    runtime = enabled.observe()
    schedule_ids = [item["scheduleId"] for item in material["members"]]
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
            AND project_id='dev-project' AND enabled AND id=ANY(%s)) AS enabled""",
            (schedule_ids, schedule_ids)).fetchone())
    expected = {item["scheduleId"]: item for item in result["members"]}
    if len(rows) != 12 or len(expected) != 12:
        raise ValueError("W5C4F_BINDING_COUNT_DRIFT")
    for row in rows:
        saved = decode_binding(row)
        entry = expected.get(saved.schedule_id)
        prior = _load("intent-" + saved.pipeline_id)["previousRef"]
        if (entry is None or row["idempotency_key"] != _key(saved.pipeline_id)
                or saved.installation_id != prepared.registered.INSTALLATION
                or saved.generation != prepared.registered.GENERATION
                or saved.control_ref.model_dump(mode="json", by_alias=True,
                                                exclude_none=True) != control_refs[saved.pipeline_id]
                or saved.ref.model_dump(mode="json", by_alias=True,
                                        exclude_none=True) != entry["ref"]
                or str(row["binding_id"]) != prior["resourceId"].removeprefix("schedule-control-")
                or row["revision"] != prior["revision"] + 1
                or row["previous_hash"] != prior["contentHash"]):
            raise ValueError("W5C4F_BINDING_AUTHORITY_DRIFT")
    if (state != {"occupied": 0, "enabled": 0}
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]
            or resumed.audit()["outcome"] != "W5C3X_RESUME_GREEN"
            or retired.audit()["outcome"] != "W5C4A_DR_DEFINITION_RETIRED_GREEN"):
        raise ValueError("W5C4F_BINDING_POST_GATE_DRIFT")
    return {"outcome": "W5C4F_TWELVE_BINDINGS_GREEN", "bindings": 12,
            "currentMembers": 0, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "issue", "audit"))
    phase = parser.parse_args().phase
    value = globals()[phase]()
    if phase == "preflight":
        value = {key: item for key, item in value.items() if key != "members"} | {
            "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
