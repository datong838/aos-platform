#!/usr/bin/env python3
"""Issue twelve runtime controls pinned to exact new selection revisions."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4d_successor_selections as selections
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c4a_dr_definition_retire as retired
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4e-successor-controls")


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
        raise ValueError("W5C4E_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _key(pipeline):
    index = pipeline.split("-", 1)[0].lower()
    if index not in {f"p{i:02d}" for i in range(1, 13)}:
        raise ValueError("W5C4E_CANONICAL_PIPELINE_REQUIRED")
    return f"a0v-w5c4e-control-{index}-20260924-v1"


def preflight():
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
    if selections.audit()["outcome"] != "W5C4D_TWELVE_SELECTIONS_GREEN":
        raise ValueError("W5C4E_SELECTION_AUTHORITY_DRIFT")
    material = selections._material()
    refs = {item["pipelineId"]: item["ref"] for item in
            selections._load("wave-result")["members"]}
    runtime = enabled.observe()
    if (len(refs) != 12 or len(material["members"]) != 12
            or runtime["host"]["pid"] != resumed._load("intent")["hostPid"]
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4E_RUNTIME_OR_MATERIAL_DRIFT")
    now, members = datetime.now(timezone.utc), []
    for item in material["members"]:
        pipeline = item["pipelineId"]
        draft = {**item["draft"],
                 "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
                 "sourceSelectionRef": refs[pipeline]}
        model = PipelineRuntimeControlDraft.model_validate_json(json.dumps(draft))
        if (model.pipeline_id != pipeline
                or model.source_selection_ref.model_dump(
                    mode="json", by_alias=True, exclude_none=True) != refs[pipeline]
                or not model.not_before <= now < model.expires_at
                or model.expires_at <= now + timedelta(hours=2)):
            raise ValueError("W5C4E_CONTROL_WINDOW_OR_REF_DRIFT")
        members.append({"pipelineId": pipeline, "scheduleId": item["scheduleId"],
                        "draft": model.model_dump(mode="json", by_alias=True,
                                                  exclude_none=True)})
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_runtime_control_revision WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS controls,
          (SELECT count(*) FROM pipeline_schedule_control_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS bindings""",
            (prepared.registered.INSTALLATION,) * 2).fetchone())
    if state != {"controls": 0, "bindings": 0}:
        raise ValueError("W5C4E_PREEXISTING_CONTROL_OR_BINDING")
    return {"outcome": "W5C4E_CONTROL_PREFLIGHT_GREEN", "members": members,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def issue():
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4E_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("wave-intent", {"hostPid": before["hostPid"],
                            "businessCounts": before["businessCounts"],
                            "expectedMembers": 12, "resend": False})
    service = prepared._plane().pipeline_control_factory.build(
        TenantScope("org-org", "dev-project"))
    refs = []
    for item in before["members"]:
        pipeline, key = item["pipelineId"], _key(item["pipelineId"])
        _write("intent-" + pipeline, {"pipelineId": pipeline,
              "scheduleId": item["scheduleId"], "draft": item["draft"],
              "idempotencyKey": key, "previousRef": None, "resend": False})
        draft = PipelineRuntimeControlDraft.model_validate_json(json.dumps(item["draft"]))
        ref = service.approve_control(draft=draft, actor=prepared.ACTOR,
                                      idempotency_key=key, previous_ref=None)
        value = ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        _write("result-" + pipeline, {"pipelineId": pipeline, "ref": value})
        refs.append({"pipelineId": pipeline, "ref": value})
    _write("wave-result", {"members": refs})
    return {"outcome": "W5C4E_CONTROLS_ACCEPTED", "members": len(refs)}


def audit():
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    material = selections._material()
    selection_refs = {item["pipelineId"]: item["ref"] for item in
                      selections._load("wave-result")["members"]}
    intent, result = _load("wave-intent"), _load("wave-result")
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute("""SELECT * FROM pipeline_runtime_control_revision
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND generation=%s ORDER BY pipeline_id,revision""",
          (prepared.registered.INSTALLATION, prepared.registered.GENERATION)).fetchall()
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_schedule_control_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS bindings,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND enabled
            AND pipeline_id IN (SELECT DISTINCT pipeline_id
              FROM pipeline_source_selection_revision WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s)) AS enabled""",
            (prepared.registered.INSTALLATION,) * 2).fetchone())
    by_pipeline = {item["pipelineId"]: item for item in result["members"]}
    drafts = {item["pipelineId"]: item["draft"] for item in material["members"]}
    if len(rows) != 12 or len(by_pipeline) != 12 or len(selection_refs) != 12:
        raise ValueError("W5C4E_CONTROL_COUNT_DRIFT")
    for row in rows:
        pipeline = row["pipeline_id"]
        saved = decode_control_row(row)
        expected = {**drafts[pipeline],
                    "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
                    "sourceSelectionRef": selection_refs[pipeline]}
        if (row["revision"] != 1 or row["idempotency_key"] != _key(pipeline)
                or saved.ref.model_dump(mode="json", by_alias=True, exclude_none=True)
                    != by_pipeline[pipeline]["ref"]
                or saved.draft.model_dump(mode="json", by_alias=True, exclude_none=True)
                    != expected):
            raise ValueError("W5C4E_CONTROL_AUTHORITY_DRIFT")
    if (state != {"bindings": 0, "enabled": 0}
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]
            or resumed.audit()["outcome"] != "W5C3X_RESUME_GREEN"
            or retired.audit()["outcome"] != "W5C4A_DR_DEFINITION_RETIRED_GREEN"):
        raise ValueError("W5C4E_CONTROL_POST_GATE_DRIFT")
    return {"outcome": "W5C4E_TWELVE_CONTROLS_GREEN", "controls": 12,
            "bindings": 0, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "issue", "audit"))
    phase = parser.parse_args().phase
    value = globals()[phase]()
    if phase == "preflight":
        value = {key: item for key, item in value.items() if key != "members"} | {
            "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
