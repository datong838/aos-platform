#!/usr/bin/env python3
"""Request one natural Host configure for the staged third successor."""

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

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3l-natural-configure")
KEY = "a0v-w5c3l-third-successor-configure-20260924-v1"


def _held(resources):
    return (len(resources) == 3
            and all(r["cleanup_state"] == "pending" and r["observed_release"] is False
                    for r in resources))


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
        raise ValueError("W5C3L_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _operation():
    receipt = _load("result")["receipt"]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT operation_id::text,kind,status,phase,revision,failure_code
          FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s
          AND operation_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), receipt["operationId"], KEY)).fetchone()
    if row is None:
        raise ValueError("W5C3L_EXACT_OPERATION_MISSING")
    return dict(row)


def preflight():
    stage = staged.audit()
    installed = ds._current().observe_installation(staged.prior.INSTALLATION)
    binding = installed["bindings"]
    target = live._host()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
        operations = conn.execute("""SELECT count(*) AS n FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
    if (stage["installationId"] != staged.prior.INSTALLATION
            or stage["generation"] != staged.prior.GENERATION
            or installed["head"]["state"] != "active"
            or installed["head"]["etag_version"] != 5
            or len(binding) != 1 or binding[0]["revision"] != 1
            or binding[0]["execution_epoch"] != 1
            or binding[0]["enabled"] is not False
            or binding[0]["operation_fence"] is not True
            or binding[0]["desired_state"] != "disabled"
            or binding[0]["observed_state"] != "ready"
            or binding[0]["config_ref"] is not None
            or not _held(installed["resources"])
            or target["pid"] != stage["hostPid"]
            or len(target["liveTargets"]) != 1
            or target["liveTargets"][0]["generation"] != staged.prior.GENERATION
            or commands or operations):
        raise ValueError("W5C3L_CONFIGURE_GATE_DRIFT")
    return {"outcome": "W5C3L_CONFIGURE_PREFLIGHT_GREEN",
            "installationId": stage["installationId"],
            "generation": stage["generation"], "configRef": stage["configRef"],
            "hostPid": target["pid"], "installationEtag": 5, "bindingRevision": 1}


def request():
    if STATE.exists():
        raise ValueError("W5C3L_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "idempotencyKey": KEY, "resend": False})
    from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
    configuration._configure()
    _connect, activation, _authorize, service = configuration._service()
    receipt = service.request(
        installation_id=before["installationId"], kind="configure",
        **ds.SCOPE, actor=activation.ACTOR, roles=activation.ROLES,
        markings=activation.MARKINGS, idempotency_key=KEY, if_match='"5"',
        target=ConfigureTarget(generation=before["generation"],
            bindingRevision=before["bindingRevision"], configRef=before["configRef"]))
    result = {"receipt": receipt.response_json, "replayed": receipt.replayed}
    _write("result", result)
    return {"outcome": "W5C3L_CONFIGURE_ACCEPTED", **result}


def observe():
    installed = ds._current().observe_installation(staged.prior.INSTALLATION)
    return {"outcome": "W5C3L_CONFIGURE_OBSERVED", "operation": _operation(),
            "installation": installed["head"], "binding": installed["bindings"],
            "resources": installed["resources"], "host": live._host()}


def audit():
    intent, result = _load("intent"), observe()
    binding, operation = result["binding"], result["operation"]
    if (operation["kind"] != "configure" or operation["status"] != "succeeded"
            or operation["phase"] != "succeeded"
            or result["installation"]["state"] != "active"
            or result["installation"]["etag_version"] != 5
            or len(binding) != 1
            or str(binding[0]["generation"]) != intent["generation"]
            or binding[0]["config_ref"] != intent["configRef"]
            or binding[0]["enabled"] is not False
            or binding[0]["operation_fence"] is not True
            or binding[0]["desired_state"] != "disabled"
            or not _held(result["resources"])
            or result["host"]["pid"] != intent["hostPid"]
            or len(result["host"]["liveTargets"]) != 1):
        raise ValueError("W5C3L_CONFIGURE_AUDIT_NOT_GREEN")
    return {"outcome": "W5C3L_CONFIGURED_FENCED_GREEN",
            "operationId": operation["operation_id"],
            "installationId": intent["installationId"],
            "bindingRevision": binding[0]["revision"],
            "executionEpoch": binding[0]["execution_epoch"],
            "observedState": binding[0]["observed_state"],
            "hostPid": intent["hostPid"], "schedulesEnabled": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request", "observe", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
