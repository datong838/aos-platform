#!/usr/bin/env python3
"""Retire the exact failed approved successor through the original installation Owner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5b_ds_settlement as ds
import a0v_w5c1_successor_approval as successor
import a0v_w5c2b_identity_recovery as identity
import a0v_w5c3b_successor_lifecycle as preparation

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3c-failed-retirement")
KEY = "a0v-w5c3c-retire-failed-prepare-20260924-v1"
OPERATION = "b5175270-7de4-4608-b6aa-6a9713b66845"


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
        raise ValueError("W5C3C_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _baseline():
    installation_id = successor._load("result")["installationId"]
    current = ds._current()
    new = current.observe_installation(installation_id)
    old = current.observe_installation(ds.DS_ID)
    host = preparation._host()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        routes = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE handler_kind='legacy' AND operation_fence
            AND installation_id IS NULL) AS legacy
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""", (*ds.SCOPE.values(), successor.GROUP)).fetchone()
        schedules = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE enabled) AS enabled FROM meta_schedule
          WHERE org_id=%s AND project_id=%s AND pipeline_id IN
          (SELECT pipeline_id FROM pipeline_source_selection_revision WHERE org_id=%s
            AND project_id=%s AND installation_id=%s AND generation=%s)""",
          (*ds.SCOPE.values(), *ds.SCOPE.values(), ds.DS_ID, ds.GENERATION)).fetchone()
        attempts = conn.execute("""SELECT count(*) AS n
          FROM extension_runtime_execution_attempt WHERE org_id=%s AND project_id=%s
          AND installation_id=%s""", (*ds.SCOPE.values(), installation_id)).fetchone()["n"]
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
        counts = conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_controlled_source_claim) AS claims,
          (SELECT count(*) FROM meta_schedule_run) AS runs""").fetchone()
    return {"installationId": installation_id, "new": new, "old": old,
            "host": host, "routes": dict(routes), "schedules": dict(schedules),
            "attempts": attempts, "commands": commands, "counts": dict(counts)}


def _require(value, *, retired):
    new = value["new"]
    operation = new["operations"]
    if (value["old"]["head"]["state"] != "uninstalled"
            or new["head"]["lock_hash"] != successor._load("result")["lockHash"]
            or new["head"]["state"] != ("uninstalled" if retired else "approved")
            or new["head"]["etag_version"] != (4 if retired else 3)
            or new["bindings"] or len(operation) != 1
            or str(operation[0]["operation_id"]) != OPERATION
            or (operation[0]["kind"], operation[0]["status"], operation[0]["phase"],
                operation[0]["revision"], operation[0]["failure_code"]) !=
               ("runtime-apply", "failed", "preparing", 7, "PREPARATION_EXECUTION_FAILED")
            or len(new["resources"]) != 3
            or any(r["cleanup_state"] != "released" or r["observed_release"] is not True
                   for r in new["resources"])
            or value["host"]["liveTargets"] != []
            or value["routes"] != {"total": 9, "legacy": 9}
            or value["schedules"] != {"total": 12, "enabled": 0}
            or value["attempts"] != 0 or new["canaryInstallations"] != 0
            or value["commands"] != (1 if retired else 0)):
        raise ValueError("W5C3C_FAILED_INSTALLATION_BOUNDARY_DRIFT")
    return value


def preflight():
    identity.verify()
    value = _require(_baseline(), retired=False)
    return {"outcome": "W5C3C_RETIRE_PREFLIGHT_GREEN",
            "installationId": value["installationId"],
            "lockHash": value["new"]["head"]["lock_hash"],
            "hostPid": value["host"]["pid"], "counts": value["counts"]}


def retire():
    if STATE.exists():
        raise ValueError("W5C3C_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "idempotencyKey": KEY, "resend": False})
    current = ds._current()
    current._installation_connection = identity.installation_connection
    legacy = current._load("a0v_ecommerce_invalid_baseline_uninstall")
    _store, service = legacy._build(current._installation_connection,
                                    current.TRUST_STATE / "signing/trust-roots.json")
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt = service.uninstall(
        **ds.SCOPE, installation_id=before["installationId"],
        request=UninstallInstallationRequest(reason="failed preparation, resources released; retire before clean successor"),
        actor="a0v-ecommerce-growth-1.4-runtime-owner", roles=["admin"], markings=[],
        idempotency_key=KEY, if_match='"3"')
    result = {"receipt": receipt.response_json, "replayed": receipt.replayed,
              "installationId": before["installationId"]}
    _write("result", result)
    return {"outcome": "W5C3C_RETIRE_RETURNED", **result}


def audit():
    intent, result = _load("intent"), _load("result")
    value = _require(_baseline(), retired=True)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        active = conn.execute("""SELECT active_revision FROM bundle_installation
          WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
          (*ds.SCOPE.values(), intent["installationId"])).fetchone()
    if (result["replayed"] is not False
            or result["installationId"] != intent["installationId"]
            or value["host"]["pid"] != intent["hostPid"]
            or value["counts"] != intent["counts"]
            or active is None or active["active_revision"] is not None):
        raise ValueError("W5C3C_RETIRE_AUDIT_NOT_GREEN")
    return {"outcome": "W5C3C_FAILED_INSTALLATION_RETIRED_GREEN",
            "installationId": intent["installationId"], "etag": 4,
            "releasedResources": 3, "routesLegacy": 9, "schedulesEnabled": 0,
            "attempts": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "retire", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
