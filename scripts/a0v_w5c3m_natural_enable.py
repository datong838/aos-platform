#!/usr/bin/env python3
"""Enable the exact live configured successor once through the original Owner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w4_dq_config_refresh as configuration
import a0v_w5b_ds_settlement as ds
import a0v_w5c3b_successor_lifecycle as live
import a0v_w5c3kr_config_stage_recovery as staged
import a0v_w5c3l_natural_configure as configured

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3m-natural-enable")
KEY = "a0v-w5c3m-third-successor-enable-20260924-v1"


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
        raise ValueError("W5C3M_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _counts():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        command = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
        operation = conn.execute("""SELECT count(*) AS n FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
        attempts = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
          (*ds.SCOPE.values(), staged.prior.INSTALLATION)).fetchone()["n"]
        routes = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE handler_kind='legacy' AND operation_fence
            AND installation_id IS NULL) AS legacy
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""",
          (*ds.SCOPE.values(), live.successor.GROUP)).fetchone()
        schedules = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE enabled) AS enabled FROM meta_schedule
          WHERE org_id=%s AND project_id=%s AND pipeline_id IN
          (SELECT pipeline_id FROM pipeline_source_selection_revision WHERE org_id=%s
            AND project_id=%s AND installation_id=%s AND generation=%s)""",
          (*ds.SCOPE.values(), *ds.SCOPE.values(), ds.DS_ID, ds.GENERATION)).fetchone()
        canary = conn.execute("""SELECT count(*) AS n FROM extension_runtime_binding
          WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
        business = conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_controlled_source_claim) AS claims,
          (SELECT count(*) FROM meta_schedule_run) AS runs""").fetchone()
    return {"commands": command, "operations": operation, "attempts": attempts,
            "routes": dict(routes), "schedules": dict(schedules),
            "canary": canary, "business": dict(business)}


def preflight():
    prior = configured.audit()
    observed = configured.observe()
    binding = observed["binding"]
    # Read the immutable Stage result through the exact recovery directory.
    with staged._configured():
        stage = staged.prior._load("result")
        stage_intent = staged.prior._load("intent")
    configuration._configure()
    current = configuration._document().model_dump(mode="json")
    counts = _counts()
    if (prior["installationId"] != staged.prior.INSTALLATION
            or prior["bindingRevision"] != 3 or prior["executionEpoch"] != 2
            or len(binding) != 1 or binding[0]["revision"] != 3
            or binding[0]["execution_epoch"] != 2
            or str(binding[0]["generation"]) != staged.prior.GENERATION
            or binding[0]["config_ref"] != stage["configRef"]
            or binding[0]["enabled"] is not False
            or binding[0]["operation_fence"] is not True
            or binding[0]["desired_state"] != "disabled"
            or observed["installation"]["etag_version"] != 5
            or not configured._held(observed["resources"])
            or observed["host"]["pid"] != prior["hostPid"]
            or len(observed["host"]["liveTargets"]) != 1
            or current != stage_intent["document"]
            or counts["commands"] or counts["operations"] or counts["attempts"]
            or counts["routes"] != {"total": 9, "legacy": 9}
            or counts["schedules"] != {"total": 12, "enabled": 0}
            or counts["canary"] != 0):
        raise ValueError("W5C3M_ENABLE_GATE_DRIFT")
    return {"outcome": "W5C3M_ENABLE_PREFLIGHT_GREEN",
            "installationId": prior["installationId"],
            "generation": staged.prior.GENERATION, "configRef": stage["configRef"],
            "hostPid": prior["hostPid"], "installationEtag": 5,
            "bindingRevision": 3, "businessCounts": counts["business"]}


def request():
    if STATE.exists():
        raise ValueError("W5C3M_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "idempotencyKey": KEY, "resend": False})
    from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
    configuration._configure()
    _connect, activation, _authorize, service = configuration._service()
    receipt = service.request(
        installation_id=before["installationId"], kind="enable", **ds.SCOPE,
        actor=activation.ACTOR, roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=KEY, if_match='"5"',
        target=ConfigureTarget(generation=before["generation"],
            bindingRevision=before["bindingRevision"], configRef=before["configRef"]))
    result = {"receipt": receipt.response_json, "replayed": receipt.replayed}
    _write("result", result)
    return {"outcome": "W5C3M_ENABLE_ACCEPTED", **result}


def observe():
    receipt = _load("result")["receipt"]
    installation = ds._current().observe_installation(staged.prior.INSTALLATION)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        operation = conn.execute("""SELECT operation_id::text,kind,status,phase,revision,failure_code
          FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s
          AND operation_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), receipt["operationId"], KEY)).fetchone()
    if operation is None:
        raise ValueError("W5C3M_EXACT_OPERATION_MISSING")
    return {"outcome": "W5C3M_ENABLE_OBSERVED", "operation": dict(operation),
            "installation": installation["head"], "binding": installation["bindings"],
            "resources": installation["resources"], "host": live._host(),
            "counts": _counts()}


def audit():
    intent, value = _load("intent"), observe()
    binding, operation = value["binding"], value["operation"]
    if (operation["kind"] != "enable" or operation["status"] != "succeeded"
            or operation["phase"] != "succeeded"
            or value["installation"]["state"] != "active"
            or value["installation"]["etag_version"] != 5
            or len(binding) != 1
            or str(binding[0]["generation"]) != intent["generation"]
            or binding[0]["config_ref"] != intent["configRef"]
            or binding[0]["enabled"] is not True
            or binding[0]["operation_fence"] is not False
            or binding[0]["desired_state"] != "enabled"
            or binding[0]["observed_state"] != "ready"
            or not configured._held(value["resources"])
            or value["host"]["pid"] != intent["hostPid"]
            or len(value["host"]["liveTargets"]) != 1
            or value["counts"] != {"commands": 1, "operations": 1, "attempts": 0,
                                   "routes": {"total": 9, "legacy": 9},
                                   "schedules": {"total": 12, "enabled": 0},
                                   "canary": 0, "business": intent["businessCounts"]}):
        raise ValueError("W5C3M_ENABLE_AUDIT_NOT_GREEN")
    return {"outcome": "W5C3M_ENABLED_LIVE_GREEN",
            "operationId": operation["operation_id"],
            "installationId": intent["installationId"],
            "bindingRevision": binding[0]["revision"],
            "executionEpoch": binding[0]["execution_epoch"],
            "hostPid": intent["hostPid"], "schedulesEnabled": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request", "observe", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
