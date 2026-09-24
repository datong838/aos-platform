#!/usr/bin/env python3
"""Issue exact successor preparation through the original Owner; never consume it locally."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from a0v_formal_text_model_renewal import database_connect
import a0v_w5b_ds_settlement as ds
import a0v_w5c1_successor_approval as successor

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3b-successor-lifecycle")
STATUS = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
          "20260924-w5c3a-host/runtime-host-status.json")
HOST_LABEL = "com.aos.a0v-w5c3-runtime-host"
KEYS = {"prepare": "a0v-w5c3b-successor-prepare-20260924-v1",
        "verify": "a0v-w5c3b-successor-verify-20260924-v1"}


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
        raise ValueError("W5C3B_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _host():
    if not STATUS.is_file():
        raise ValueError("W5C3B_HOST_STATUS_MISSING")
    value = json.loads(STATUS.read_text())
    listing = subprocess.run(["launchctl", "list"], capture_output=True, text=True,
                             check=True).stdout.splitlines()
    rows = [row.split() for row in listing if row.rstrip().endswith(HOST_LABEL)]
    if (len(rows) != 1 or len(rows[0]) != 3 or not rows[0][0].isdigit()
            or value.get("outcome") != "RUNTIME_HOST_ACTIVE"
            or value.get("pid") != int(rows[0][0])
            or value.get("positiveTenant") != "org-org/dev-project"
            or value.get("canaryTenantCount") != 0):
        raise ValueError("W5C3B_UNIQUE_HOST_DRIFT")
    os.kill(value["pid"], 0)
    return {"pid": value["pid"], "liveTargets": value.get("liveTargets")}


def _facts():
    current = ds._current()
    approved = successor._load("result")
    installation_id = approved["installationId"]
    new = current.observe_installation(installation_id)
    old = current.observe_installation(ds.DS_ID)
    host = _host()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        routes = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE handler_kind='legacy' AND operation_fence
            AND installation_id IS NULL) AS legacy
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""", (*ds.SCOPE.values(), successor.GROUP)).fetchone()
        schedules = conn.execute("""SELECT count(*) AS total,count(*) FILTER(WHERE enabled) AS enabled
          FROM meta_schedule WHERE org_id=%s AND project_id=%s AND pipeline_id IN
          (SELECT pipeline_id FROM pipeline_source_selection_revision WHERE org_id=%s
            AND project_id=%s AND installation_id=%s AND generation=%s)""",
          (*ds.SCOPE.values(), *ds.SCOPE.values(), ds.DS_ID, ds.GENERATION)).fetchone()
        canary = conn.execute("""SELECT count(*) AS n FROM bundle_installation
          WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
        budget = conn.execute("""SELECT r.revision,r.effective_until>clock_timestamp() AS valid
          FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r
          ON (r.org_id,r.project_id,r.policy_id,r.revision)=
             (h.org_id,h.project_id,h.policy_id,h.current_revision)
          WHERE h.org_id=%s AND h.project_id=%s AND h.policy_id=%s""",
          (*ds.SCOPE.values(), "a0v-ecommerce-budget-policy-v1")).fetchone()
    if (old["head"]["state"] != "uninstalled"
            or new["head"]["lock_hash"] != approved["lockHash"]
            or dict(routes) != {"total": 9, "legacy": 9}
            or dict(schedules) != {"total": 12, "enabled": 0}
            or canary != 0 or budget is None or budget["revision"] != 13
            or budget["valid"] is not True):
        raise ValueError("W5C3B_SAFETY_BASELINE_DRIFT")
    return {"installationId": installation_id, "new": new, "old": old,
            "host": host, "routesLegacy": 9, "schedulesEnabled": 0, "canary": 0}


def _operation(stage):
    result = _load(stage + "-result")
    operation_id = result["receipt"]["operationId"]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT operation_id::text,kind,status,phase,revision,
          failure_code,deadline<clock_timestamp() AS expired FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), operation_id, KEYS[stage])).fetchone()
    if row is None:
        raise ValueError("W5C3B_EXACT_OPERATION_MISSING")
    return dict(row)


def preflight_prepare():
    state = _facts()
    new = state["new"]
    if (new["head"]["state"] != "approved" or new["head"]["etag_version"] != 3
            or new["bindings"] or new["operations"] or new["resources"]
            or state["host"]["liveTargets"] != []):
        raise ValueError("W5C3B_PREPARE_GATE_DRIFT")
    return {"outcome": "W5C3B_PREPARE_PREFLIGHT_GREEN",
            "installationId": state["installationId"], "hostPid": state["host"]["pid"],
            "etag": 3, "liveTargets": 0}


def request_prepare():
    if (STATE / "prepare-intent.json").exists():
        raise ValueError("W5C3B_PREPARE_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight_prepare()
    _write("prepare-intent", {**before, "idempotencyKey": KEYS["prepare"], "resend": False})
    current = ds._current()
    activation, _store, lifecycle, _disable, _dependent = current._setup_runtime_plane()
    receipt = lifecycle.request_preparation(
        **ds.SCOPE, installation_id=before["installationId"], kind="runtime-apply",
        actor=activation.ACTOR, roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=KEYS["prepare"], if_match='"3"')
    result = {"receipt": receipt.response_json, "replayed": receipt.replayed}
    _write("prepare-result", result)
    return {"outcome": "W5C3B_PREPARE_ACCEPTED", **result}


def observe_prepare():
    state, operation = _facts(), _operation("prepare")
    return {"outcome": "W5C3B_PREPARE_OBSERVED", "operation": operation,
            "installationState": state["new"]["head"]["state"],
            "etag": state["new"]["head"]["etag_version"],
            "resources": len(state["new"]["resources"]),
            "host": state["host"]}


def preflight_verify():
    observed = observe_prepare()
    state = _facts()
    new, host = state["new"], state["host"]
    targets = host["liveTargets"]
    if (observed["operation"]["kind"] != "runtime-apply"
            or observed["operation"]["status"] != "succeeded"
            or new["head"]["state"] != "applied" or new["head"]["etag_version"] != 4
            or new["bindings"] or len(new["resources"]) != 3
            or any(r["cleanup_state"] == "released" or r["observed_release"] is True
                   for r in new["resources"])
            or len(targets) != 1 or targets[0]["installationId"] != state["installationId"]
            or targets[0]["tenant"] != ["org-org", "dev-project"]):
        raise ValueError("W5C3B_VERIFY_GATE_DRIFT")
    intent = _load("prepare-intent")
    if host["pid"] != intent["hostPid"]:
        raise ValueError("W5C3B_PREPARED_JOB_OWNER_LOST")
    return {"outcome": "W5C3B_VERIFY_PREFLIGHT_GREEN",
            "installationId": state["installationId"], "hostPid": host["pid"],
            "generation": targets[0]["generation"], "etag": 4}


def request_verify():
    if (STATE / "verify-intent.json").exists():
        raise ValueError("W5C3B_VERIFY_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight_verify()
    _write("verify-intent", {**before, "idempotencyKey": KEYS["verify"], "resend": False})
    current = ds._current()
    activation, _store, lifecycle, _disable, _dependent = current._setup_runtime_plane()
    receipt = lifecycle.request_preparation(
        **ds.SCOPE, installation_id=before["installationId"], kind="runtime-verify",
        actor=activation.ACTOR, roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=KEYS["verify"], if_match='"4"')
    result = {"receipt": receipt.response_json, "replayed": receipt.replayed}
    _write("verify-result", result)
    return {"outcome": "W5C3B_VERIFY_ACCEPTED", **result}


def observe_verify():
    state, operation = _facts(), _operation("verify")
    return {"outcome": "W5C3B_VERIFY_OBSERVED", "operation": operation,
            "installationState": state["new"]["head"]["state"],
            "etag": state["new"]["head"]["etag_version"],
            "binding": state["new"]["bindings"], "resources": state["new"]["resources"],
            "host": state["host"]}


def audit():
    result = observe_verify()
    intent = _load("verify-intent")
    binding = result["binding"]
    if (result["operation"]["kind"] != "runtime-verify"
            or result["operation"]["status"] != "succeeded"
            or result["installationState"] != "active" or result["etag"] != 5
            or len(binding) != 1 or str(binding[0]["generation"]) != intent["generation"]
            or binding[0]["enabled"] is not False or binding[0]["operation_fence"] is not True
            or len(result["resources"]) != 3
            or any(r["cleanup_state"] == "released" or r["observed_release"] is True
                   for r in result["resources"])
            or result["host"]["pid"] != intent["hostPid"]
            or len(result["host"]["liveTargets"]) != 1
            or result["host"]["liveTargets"][0]["generation"] != intent["generation"]):
        raise ValueError("W5C3B_PREPARE_VERIFY_AUDIT_NOT_GREEN")
    return {"outcome": "W5C3B_LIVE_PREPARED_JOB_GREEN",
            "installationId": intent["installationId"], "generation": intent["generation"],
            "hostPid": intent["hostPid"], "bindingRevision": binding[0]["revision"],
            "executionEpoch": binding[0]["execution_epoch"],
            "schedulesEnabled": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight_prepare", "request_prepare",
                "observe_prepare", "preflight_verify", "request_verify", "observe_verify", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
