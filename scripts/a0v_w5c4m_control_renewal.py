#!/usr/bin/env python3
"""Append twelve runtime controls referencing renewed selections, once."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import decode_control_row
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c4e_successor_controls as prior
import a0v_w5c4l_selection_renewal as selections

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4m-control-renewal")


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
        raise ValueError("W5C4M_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _key(pipeline):
    prefix = pipeline.split("-", 1)[0].lower()
    if prefix not in {f"p{i:02d}" for i in range(1, 13)}:
        raise ValueError("W5C4M_CANONICAL_PIPELINE_REQUIRED")
    return f"a0v-w5c4m-control-{prefix}-20260924-v1"


def preflight():
    if selections.audit()["outcome"] != "W5C4L_TWELVE_SELECTION_REV2_GREEN":
        raise ValueError("W5C4M_SELECTION_DRIFT")
    material = selections._material()
    selection_refs = {m["pipelineId"]: m["ref"] for m in
                      selections._load("wave-result")["members"]}
    old_refs = {m["pipelineId"]: m["ref"] for m in
                prior._load("wave-result")["members"]}
    runtime = enabled.observe()
    now = datetime.now(timezone.utc)
    if (len(selection_refs) != 12 or len(old_refs) != 12
            or runtime["host"]["pid"] != material["hostPid"]
            or runtime["counts"]["business"] != material["businessCounts"]
            or runtime["counts"]["attempts"] != 0
            or runtime["counts"]["canary"] != 0
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4M_RUNTIME_OR_REFS_DRIFT")
    members = []
    for item in material["members"]:
        pipeline = item["pipelineId"]
        draft = {**item["draft"],
            "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
            "sourceSelectionRef": selection_refs[pipeline]}
        model = PipelineRuntimeControlDraft.model_validate_json(json.dumps(draft))
        if (model.pipeline_id != pipeline
                or not model.not_before <= now < model.expires_at - timedelta(hours=2)):
            raise ValueError("W5C4M_CONTROL_DRAFT_DRIFT")
        members.append({"pipelineId": pipeline, "draft": model.model_dump(
            mode="json", by_alias=True, exclude_none=True),
            "previousRef": old_refs[pipeline]})
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute("""SELECT DISTINCT ON (pipeline_id) *
          FROM pipeline_runtime_control_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s AND generation=%s
          ORDER BY pipeline_id,revision DESC""",
          (prepared.registered.INSTALLATION, prepared.registered.GENERATION)).fetchall()
        keys = conn.execute("""SELECT count(*) AS n FROM pipeline_runtime_control_revision
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND idempotency_key=ANY(%s)""",
          (prepared.registered.INSTALLATION, [_key(m["pipelineId"]) for m in members])
          ).fetchone()["n"]
    expected = {m["pipelineId"]: m for m in members}
    if len(rows) != 12 or keys:
        raise ValueError("W5C4M_CURRENT_CONTROL_OR_KEY_DRIFT")
    for row in rows:
        item = expected.get(row["pipeline_id"])
        if (item is None or row["revision"] != 1
                or decode_control_row(row).ref.model_dump(
                    mode="json", by_alias=True, exclude_none=True) != item["previousRef"]):
            raise ValueError("W5C4M_PREDECESSOR_DRIFT")
    return {"outcome": "W5C4M_CONTROL_PREFLIGHT_GREEN", "members": members,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def issue():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4M_INTENT_EXISTS_RECONCILE_FIRST")
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
        ref = service.approve_control(
            draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(item["draft"])),
            actor=prepared.ACTOR, idempotency_key=_key(pipeline),
            previous_ref=item["previousRef"])
        value = ref.model_dump(mode="json", by_alias=True, exclude_none=True)
        _write("result-" + pipeline, {"pipelineId": pipeline, "ref": value})
        refs.append({"pipelineId": pipeline, "ref": value})
    _write("wave-result", {"members": refs})
    return {"outcome": "W5C4M_CONTROLS_ACCEPTED", "members": len(refs)}


def audit():
    material, intent, result = selections._material(), _load("wave-intent"), _load("wave-result")
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
            AND project_id='dev-project' AND enabled AND pipeline_id=ANY(%s)) AS enabled""",
          (prepared.registered.INSTALLATION,
           [m["pipelineId"] for m in material["members"]])).fetchone())
    expected = {m["pipelineId"]: m for m in material["members"]}
    refs = {m["pipelineId"]: m["ref"] for m in result["members"]}
    selections_refs = {m["pipelineId"]: m["ref"] for m in
                       selections._load("wave-result")["members"]}
    if len(rows) != 24 or len(refs) != 12:
        raise ValueError("W5C4M_CONTROL_COUNT_DRIFT")
    for row in rows:
        if row["revision"] == 1:
            continue
        pipeline = row["pipeline_id"]
        saved = decode_control_row(row)
        previous = _load("intent-" + pipeline)["previousRef"]
        if (pipeline not in expected or row["revision"] != 2
                or row["idempotency_key"] != _key(pipeline)
                or row["previous_hash"] != previous["contentHash"]
                or saved.ref.model_dump(mode="json", by_alias=True,
                                        exclude_none=True) != refs[pipeline]
                or saved.draft.source_selection_ref.model_dump(
                    mode="json", by_alias=True, exclude_none=True) != selections_refs[pipeline]
                or saved.draft.model_dump(mode="json", by_alias=True,
                                          exclude_none=True) != _load("intent-" + pipeline)["draft"]):
            raise ValueError("W5C4M_CONTROL_AUTHORITY_DRIFT")
    if (state != {"bindings": 12, "enabled": 0}
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C4M_CONTROL_POST_GATE_DRIFT")
    return {"outcome": "W5C4M_TWELVE_CONTROL_REV2_GREEN",
            "controlRows": 24, "bindings": 12, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "issue", "audit"))
    value = globals()[parser.parse_args().phase]()
    if value.get("outcome") == "W5C4M_CONTROL_PREFLIGHT_GREEN":
        value = {**value, "members": len(value["members"])}
    print(json.dumps(value, ensure_ascii=False, default=str))
