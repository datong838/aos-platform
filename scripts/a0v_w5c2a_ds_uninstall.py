#!/usr/bin/env python3
"""Uninstall the drained DS predecessor through its original Owner once."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5b_ds_settlement as ds
import a0v_w5c1_successor_approval as successor

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c2a-ds-uninstall")
KEY = "a0v-w5c2a-ds-uninstall-20260924-v1"


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
        raise ValueError("W5C2A_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    approved = successor.audit()
    state = ds.snapshot()
    installation = state["installation"]
    binding = installation["bindings"]
    if (installation["head"]["state"] != "active"
            or installation["head"]["etag_version"] != 5
            or installation["head"]["lock_hash"] != ds.LOCK
            or len(binding) != 1 or str(binding[0]["generation"]) != ds.GENERATION
            or (binding[0]["revision"], binding[0]["execution_epoch"]) != (13, 7)
            or binding[0]["enabled"] is not False or binding[0]["operation_fence"] is not True
            or binding[0]["desired_state"] != "disabled"
            or len(installation["resources"]) != 3
            or any(r["cleanup_state"] != "released" or r["observed_release"] is not True
                   for r in installation["resources"])
            or any(r["status"] not in {"succeeded", "failed", "cancelled"}
                   for r in installation["operations"])
            or state["schedules"] != {"total": 12, "enabled": 0}
            or state["activeAttempts"] != 0 or state["canaryBindings"] != 0):
        raise ValueError("W5C2A_PREDECESSOR_DRIFT")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        receipt = conn.execute("""SELECT content_hash FROM extension_dispatch_lifecycle_receipt
          WHERE org_id=%s AND project_id=%s AND runtime_operation_id=%s AND phase='detach'""",
          (*ds.SCOPE.values(), successor.DETACH_OPERATION)).fetchone()
        gate = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_claim_gate
          WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s""",
          (*ds.SCOPE.values(), successor.GROUP)).fetchone()["n"]
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
    if receipt is None or receipt["content_hash"] != successor.DETACH_HASH or gate or commands:
        raise ValueError("W5C2A_DETACH_OR_COMMAND_DRIFT")
    return {"outcome": "W5C2A_PREFLIGHT_GREEN", "installationId": ds.DS_ID,
            "successorInstallationId": approved["installationId"],
            "predecessorEtag": 5, "bindingRevision": 13,
            "detachReceiptHash": successor.DETACH_HASH,
            "schedulesEnabled": 0, "activeAttempts": 0, "canary": 0}


def uninstall():
    if STATE.exists():
        raise ValueError("W5C2A_EXISTING_INTENT_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "idempotencyKey": KEY, "resend": False})
    current = ds._current()
    legacy = current._load("a0v_ecommerce_invalid_baseline_uninstall")
    store, service = legacy._build(current._installation_connection,
                                   current.TRUST_STATE / "signing/trust-roots.json")
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt = service.uninstall(
        **ds.SCOPE, installation_id=ds.DS_ID,
        request=UninstallInstallationRequest(
            reason="DS disabled, detached and released; approved direct successor exists"),
        actor="a0v-ecommerce-growth-1.4-runtime-owner", roles=["admin"], markings=[],
        idempotency_key=KEY, if_match='"5"')
    result = {"receipt": receipt.response_json, "replayed": receipt.replayed,
              "installationId": ds.DS_ID,
              "successorInstallationId": before["successorInstallationId"]}
    _write("result", result)
    return {"outcome": "W5C2A_UNINSTALL_RETURNED", **result}


def audit():
    result = _load("result")
    current = ds._current()
    old = current.observe_installation(ds.DS_ID)
    new = current.observe_installation(result["successorInstallationId"])
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = conn.execute("""SELECT active_revision FROM bundle_installation
          WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
          (*ds.SCOPE.values(), ds.DS_ID)).fetchone()
        receipt = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*ds.SCOPE.values(), KEY)).fetchone()["n"]
        routes = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE handler_kind='legacy' AND operation_fence
            AND installation_id IS NULL) AS legacy
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""", (*ds.SCOPE.values(), successor.GROUP)).fetchone()
        schedule = conn.execute("""SELECT count(*) AS total,count(*) FILTER(WHERE enabled) AS enabled
          FROM meta_schedule WHERE org_id=%s AND project_id=%s AND pipeline_id IN
          (SELECT pipeline_id FROM pipeline_source_selection_revision
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s)""",
          (*ds.SCOPE.values(), *ds.SCOPE.values(), ds.DS_ID, ds.GENERATION)).fetchone()
        active = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s
          AND state IN ('running','claimed','unknown')""",
          (*ds.SCOPE.values(), ds.DS_ID)).fetchone()["n"]
        canary = conn.execute("""SELECT count(*) AS n FROM bundle_installation
          WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
    if (result["replayed"] is not False or old["head"]["state"] != "uninstalled"
            or head is None or head["active_revision"] is not None or receipt != 1
            or new["head"]["state"] != "approved" or new["head"]["etag_version"] != 3
            or new["bindings"] or new["operations"] or new["resources"]
            or dict(routes) != {"total": 9, "legacy": 9}
            or dict(schedule) != {"total": 12, "enabled": 0}
            or active != 0 or canary != 0):
        raise ValueError("W5C2A_UNINSTALL_AUDIT_NOT_GREEN")
    return {"outcome": "W5C2A_DS_UNINSTALLED_GREEN", "predecessor": ds.DS_ID,
            "successor": result["successorInstallationId"],
            "successorState": "approved", "routesLegacy": 9,
            "schedulesEnabled": 0, "activeAttempts": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "uninstall", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
