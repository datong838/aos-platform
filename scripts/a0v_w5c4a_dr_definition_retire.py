#!/usr/bin/env python3
"""Retire the disabled DR definition once through its original Owner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3z_retirement_feasibility as prior
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4a-dr-definition-retire")
KEY = "a0v-w5c4a-old-dr-definition-retire-20260924-v1"


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
        raise ValueError("W5C4A_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    value = prior.inventory()
    runtime = enabled.observe()
    if (value["outcome"] != "W5C3Z_RETIREMENT_FEASIBILITY_READ"
            or value["head"]["definition_id"] != prior.DEFINITION
            or value["head"]["revision"] != 3
            or value["head"]["content_hash"] !=
                "sha256:48e236e8e5951defd0cb91cd9d52afc8bec287241804bd3202713ae03cfc22bd"
            or value["head"]["state"] != "disabled"
            or value["runs"]["retirement_blocking"] != 0
            or value["claims"]["unfinished_groups"] != 0
            or value["actorRole"] != "admin"
            or value["currentMembers"] != 12 or value["schedulesEnabled"] != 0
            or runtime["host"]["pid"] != resumed._load("intent")["hostPid"]
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4A_RETIRE_GATE_DRIFT")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        count = conn.execute("""SELECT count(*) AS n
          FROM pipeline_snapshot_schedule_definition_revision
          WHERE org_id='org-org' AND project_id='dev-project'
            AND definition_id=%s AND idempotency_key=%s""",
          (prior.DEFINITION, KEY)).fetchone()["n"]
    if count != 0:
        raise ValueError("W5C4A_RETIRE_KEY_ALREADY_USED")
    return {"outcome": "W5C4A_RETIRE_PREFLIGHT_GREEN",
            "definitionId": prior.DEFINITION,
            "expectedRef": {"resourceType": "SnapshotScheduleDefinitionRevision",
                "resourceId": "snapshot-schedule-" + prior.DEFINITION,
                "revision": 3, "contentHash": value["head"]["content_hash"]},
            "idempotencyKey": KEY, "actor": prior.ACTOR,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def retire():
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4A_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=False)
    result = service.transition(definition_id=prior.DEFINITION, actor=prior.ACTOR,
        intent="retire", expected_ref=before["expectedRef"], idempotency_key=KEY)
    _write("result", result)
    return {"outcome": "W5C4A_RETIRE_ACCEPTED", "ref": result["ref"],
            "state": result["body"]["state"]}


def audit():
    intent, result = _load("intent"), _load("result")
    runtime = enabled.observe()
    cutover = resumed.audit()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = dict(conn.execute("""SELECT revision,content_hash,state
          FROM pipeline_snapshot_schedule_definition_head
          WHERE org_id='org-org' AND project_id='dev-project' AND definition_id=%s""",
          (prior.DEFINITION,)).fetchone())
        revision = [dict(row) for row in conn.execute("""SELECT revision,content_hash,idempotency_key
          FROM pipeline_snapshot_schedule_definition_revision
          WHERE org_id='org-org' AND project_id='dev-project'
            AND definition_id=%s AND idempotency_key=%s""",
          (prior.DEFINITION, KEY)).fetchall()]
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_current_member
            WHERE org_id='org-org' AND project_id='dev-project'
            AND definition_id=%s) AS occupied,
          (SELECT count(*) FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND enabled
            AND pipeline_id IN (SELECT DISTINCT pipeline_id
              FROM pipeline_source_selection_revision WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s)) AS enabled""",
          (prior.DEFINITION, "c6812824-a0c3-4adc-9ebc-d56178ae135c")).fetchone())
    if (head != {"revision": 4, "content_hash": result["ref"]["contentHash"],
                 "state": "retired"}
            or revision != [{"revision": 4,
                             "content_hash": result["ref"]["contentHash"],
                             "idempotency_key": KEY}]
            or state != {"occupied": 0, "enabled": 0}
            or result["body"]["state"] != "retired"
            or cutover["outcome"] != "W5C3X_RESUME_GREEN"
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C4A_RETIRE_AUDIT_DRIFT")
    return {"outcome": "W5C4A_DR_DEFINITION_RETIRED_GREEN",
            "definitionId": prior.DEFINITION, "revision": 4,
            "releasedMembers": 12, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "retire", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
