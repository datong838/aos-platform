#!/usr/bin/env python3
"""Issue twelve exact successor selections once, with per-member frozen boundaries."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4c_controls_preflight as dry
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c4a_dr_definition_retire as retired
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4d-successor-selections")


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
        raise ValueError("W5C4D_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _material():
    path = dry.STATE / "material.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C4D_DRY_MATERIAL_REQUIRED")
    return json.loads(path.read_text())


def _key(pipeline):
    index = pipeline.split("-", 1)[0].lower()
    if index not in {f"p{i:02d}" for i in range(1, 13)}:
        raise ValueError("W5C4D_CANONICAL_PIPELINE_REQUIRED")
    return f"a0v-w5c4d-selection-{index}-20260924-v1"


def preflight():
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    material = _material()
    runtime = enabled.observe()
    if (resumed.audit()["outcome"] != "W5C3X_RESUME_GREEN"
            or retired.audit()["outcome"] != "W5C4A_DR_DEFINITION_RETIRED_GREEN"
            or material["installationId"] != prepared.registered.INSTALLATION
            or material["generation"] != prepared.registered.GENERATION
            or material["executionEpoch"] != 3
            or len(material["members"]) != 12
            or len({item["pipelineId"] for item in material["members"]}) != 12
            or runtime["host"]["pid"] != resumed._load("intent")["hostPid"]
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4D_SELECTION_GATE_DRIFT")
    now = datetime.now(timezone.utc)
    for item in material["members"]:
        draft = PipelineSourceSelectionDraft.model_validate_json(json.dumps(item["draft"]))
        if (draft.pipeline_id != item["pipelineId"]
                or draft.installation_ref.installation_id != prepared.registered.INSTALLATION
                or draft.generation != prepared.registered.GENERATION
                or draft.configuration_ref.model_dump(mode="json", by_alias=True) != material["configRef"]
                or not draft.not_before <= now < draft.expires_at
                or draft.expires_at <= now + timedelta(hours=2)):
            raise ValueError("W5C4D_DRAFT_WINDOW_OR_AUTHORITY_DRIFT")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_source_selection_revision WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS selections,
          (SELECT count(*) FROM pipeline_runtime_control_revision WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS controls,
          (SELECT count(*) FROM pipeline_schedule_control_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS bindings""",
            (prepared.registered.INSTALLATION,) * 3).fetchone())
    if state != {"selections": 0, "controls": 0, "bindings": 0}:
        raise ValueError("W5C4D_PREEXISTING_CONTROL_CHAIN")
    return {"outcome": "W5C4D_SELECTION_PREFLIGHT_GREEN",
            "members": material["members"], "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def issue():
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4D_INTENT_EXISTS_RECONCILE_FIRST")
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
        draft = PipelineSourceSelectionDraft.model_validate_json(json.dumps(item["draft"]))
        ref = service.approve_selection(draft=draft, actor=prepared.ACTOR,
                                        idempotency_key=key, previous_ref=None)
        value = ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        _write("result-" + pipeline, {"pipelineId": pipeline, "ref": value})
        refs.append({"pipelineId": pipeline, "ref": value})
    _write("wave-result", {"members": refs})
    return {"outcome": "W5C4D_SELECTIONS_ACCEPTED", "members": len(refs)}


def audit():
    from aos_api.pipeline_source_selection_store import decode_selection_row
    material = _material()
    intent, result = _load("wave-intent"), _load("wave-result")
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute("""SELECT * FROM pipeline_source_selection_revision
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND generation=%s ORDER BY pipeline_id,revision""",
          (prepared.registered.INSTALLATION, prepared.registered.GENERATION)).fetchall()
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_runtime_control_revision WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS controls,
          (SELECT count(*) FROM pipeline_schedule_control_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) AS bindings,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND enabled
            AND pipeline_id IN (SELECT DISTINCT pipeline_id
              FROM pipeline_source_selection_revision WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s)) AS enabled""",
            (prepared.registered.INSTALLATION,) * 3).fetchone())
    by_pipeline = {item["pipelineId"]: item for item in result["members"]}
    expected = {item["pipelineId"]: item for item in material["members"]}
    if len(rows) != 12 or len(by_pipeline) != 12 or len(expected) != 12:
        raise ValueError("W5C4D_SELECTION_COUNT_DRIFT")
    for row in rows:
        pipeline = row["pipeline_id"]
        saved = decode_selection_row(row)
        if (pipeline not in by_pipeline or row["revision"] != 1
                or row["idempotency_key"] != _key(pipeline)
                or saved.ref.model_dump(mode="json", by_alias=True, exclude_none=True)
                    != by_pipeline[pipeline]["ref"]
                or saved.draft.model_dump(mode="json", by_alias=True, exclude_none=True)
                    != expected[pipeline]["draft"]):
            raise ValueError("W5C4D_SELECTION_AUTHORITY_DRIFT")
    if (state != {"controls": 0, "bindings": 0, "enabled": 0}
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]
            or resumed.audit()["outcome"] != "W5C3X_RESUME_GREEN"
            or retired.audit()["outcome"] != "W5C4A_DR_DEFINITION_RETIRED_GREEN"):
        raise ValueError("W5C4D_SELECTION_POST_GATE_DRIFT")
    return {"outcome": "W5C4D_TWELVE_SELECTIONS_GREEN", "selections": 12,
            "controls": 0, "bindings": 0, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "issue", "audit"))
    phase = parser.parse_args().phase
    value = globals()[phase]()
    if phase == "preflight":
        value = {key: item for key, item in value.items() if key != "members"} | {
            "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
