#!/usr/bin/env python3
"""Release DM's claimed-null-container uncertain resource and settle failed preparation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_bl_expired_attempt_recovery as runtime
import a0v_dm_replacement_recovery as dm
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery


INSTALLATION = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
OPERATION = "ec7a706f-d592-4139-9b54-67073fab064d"
RESOURCE = "4d407243-6679-49ee-9286-e21e464e0170"
STATE = Path(__file__).resolve().parents[2] / (
    ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dm"
)
EXPECTED_REVISION = 9


def facts(conn) -> dict:
    operation = dict(conn.execute("""SELECT kind,phase,status,revision,failure_code
      FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
      AND operation_id=%s""", (OPERATION,)).fetchone())
    resources = [dict(row) for row in conn.execute("""SELECT resource_id::text,cleanup_state,
      observed_release,container_id,create_claimed_at IS NOT NULL AS claimed,
      expires_at<clock_timestamp() AS expired
      FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
      AND operation_id=%s ORDER BY resource_id""", (OPERATION,)).fetchall()]
    snap = dm.replacement.load_profile().observe_installation(INSTALLATION)
    head = {"state": snap["head"]["state"], "etag_version": snap["head"]["etag_version"]}
    binds = len(snap.get("bindings") or [])
    return {"operation": operation, "resources": resources, "head": head, "bindings": binds}


def preflight() -> dict:
    connect = runtime._runtime_connect_factory()
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        value = facts(conn)
    expected_operation = {"kind": "runtime-apply", "phase": "preparing",
                          "status": "needs_attention", "revision": EXPECTED_REVISION,
                          "failure_code": "RESOURCE_CLEANUP_UNCERTAIN"}
    uncertain = [row for row in value["resources"] if row["cleanup_state"] == "uncertain"]
    released = [row for row in value["resources"] if row["cleanup_state"] == "released"]
    if (value["operation"] != expected_operation or value["head"] != {"state": "approved", "etag_version": 3}
            or value["bindings"] != 0 or len(value["resources"]) != 3 or len(uncertain) != 1
            or uncertain[0]["resource_id"] != RESOURCE or uncertain[0]["container_id"] is not None
            or uncertain[0]["claimed"] is not True or uncertain[0]["expired"] is not True
            or uncertain[0]["observed_release"] is not False or len(released) != 2
            or any(row["observed_release"] is not True for row in released)):
        raise RuntimeError("DM exact claimed-null-container uncertain boundary required")
    return {"outcome": "DM_UNCERTAIN_CLEANUP_PREFLIGHT_GREEN", "facts": value,
            "sourceReads": 0, "attemptsCreated": 0}


def recover_resource() -> dict:
    preflight()
    recovery = ExpiredResourceRecovery(
        connect=runtime._runtime_connect_factory(),
        driver=CleanupOnlyOciDriver(OciDriver(context="colima-aos-extension")),
    )
    state = recovery.run_one(org_id="org-org", project_id="dev-project", resource_id=RESOURCE)
    if state != "released":
        raise RuntimeError("DM uncertain resource did not become released")
    connect = runtime._runtime_connect_factory()
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        value = facts(conn)
    if any(row["cleanup_state"] != "released" or row["observed_release"] is not True
           for row in value["resources"]):
        raise RuntimeError("DM all resources released readback required")
    return {"outcome": "DM_UNCERTAIN_RESOURCE_RELEASED", "resourceId": RESOURCE,
            "state": state, "facts": value}


def settle_preparation() -> dict:
    connect = runtime._runtime_connect_factory()
    recovery = ExpiredResourceRecovery(
        connect=connect,
        driver=CleanupOnlyOciDriver(OciDriver(context="colima-aos-extension")),
    )
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        before = facts(conn)
        if before["operation"]["kind"] != "runtime-apply" or before["operation"]["phase"] != "preparing":
            raise RuntimeError("DM failed-preparation settle phase differs")
        if before["operation"]["status"] != "needs_attention":
            raise RuntimeError("DM failed-preparation settle status differs")
        if before["operation"]["failure_code"] != "RESOURCE_CLEANUP_UNCERTAIN":
            raise RuntimeError("DM failed-preparation settle failure differs")
        if any(row["cleanup_state"] != "released" or row["observed_release"] is not True
               for row in before["resources"]):
            raise RuntimeError("DM released resources required before settlement")
        revision = before["operation"]["revision"]
        result = recovery.settle_preparation(
            org_id="org-org", project_id="dev-project",
            operation_id=OPERATION, expected_revision=revision)
    if (str(result.operation_id), result.status) != (OPERATION, "failed"):
        raise RuntimeError("DM failed-preparation settlement differs")
    return {"outcome": "DM_FAILED_PREPARATION_SETTLED", "operationId": OPERATION,
            "status": result.status, "revision": result.revision, "phase": result.phase}


def freeze(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        raise ValueError(f"immutable {path.name} exists")
    path.write_text(json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n",
                    encoding="utf-8")
    path.chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "recover-resource", "settle-preparation"))
    args = parser.parse_args()
    action = {"preflight": preflight, "recover-resource": recover_resource,
              "settle-preparation": settle_preparation}[args.action]
    result = action()
    freeze(STATE / f"uncertain-{args.action}-result.json", result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
