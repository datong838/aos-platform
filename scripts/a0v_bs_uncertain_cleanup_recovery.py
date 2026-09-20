#!/usr/bin/env python3
"""Recover BS's one expired uncertain resource and settle its committed preparation."""
from __future__ import annotations

import argparse
import json

import a0v_bl_expired_attempt_recovery as runtime
from aos_api.extension_runtime.committed_cleanup import settle_committed_cleanup
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery


INSTALLATION = "c5a95204-c379-4763-b697-b4417349d204"
GENERATION = "6f8bcb56-5717-4d7a-9a9e-97c1982db053"
OPERATION = "0587d5e6-1f14-4406-a1e4-95e8e556c583"
RESOURCE = "accb54dc-6341-4dc7-b8da-40202a102569"


def facts(conn) -> dict:
    operation = dict(conn.execute("""SELECT kind,phase,status,revision,failure_code
      FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
      AND operation_id=%s""", (OPERATION,)).fetchone())
    binding = dict(conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,
      desired_state,observed_state FROM extension_runtime_binding
      WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
      AND generation=%s""", (INSTALLATION, GENERATION)).fetchone())
    resources = [dict(row) for row in conn.execute("""SELECT resource_id::text,cleanup_state,
      observed_release,expires_at,expires_at<clock_timestamp() expired
      FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
      AND operation_id=%s ORDER BY resource_id""", (OPERATION,)).fetchall()]
    attempts = conn.execute("""SELECT count(*) n FROM extension_runtime_execution_attempt
      WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
      AND generation=%s""", (INSTALLATION, GENERATION)).fetchone()["n"]
    return {"operation": operation, "binding": binding, "resources": resources,
            "attempts": attempts}


def preflight() -> dict:
    connect = runtime._runtime_connect_factory()
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        value = facts(conn)
    expected_operation = {"kind": "runtime-apply", "phase": "succeeded",
                          "status": "needs_attention", "revision": 20,
                          "failure_code": "RESOURCE_CLEANUP_UNCERTAIN"}
    expected_binding = {"revision": 7, "execution_epoch": 4, "enabled": False,
                        "operation_fence": True, "desired_state": "enabled",
                        "observed_state": "unknown"}
    uncertain = [row for row in value["resources"] if row["cleanup_state"] == "uncertain"]
    released = [row for row in value["resources"] if row["cleanup_state"] == "released"]
    if (value["operation"] != expected_operation or value["binding"] != expected_binding
            or value["attempts"] != 0 or len(value["resources"]) != 3 or len(uncertain) != 1
            or uncertain[0]["resource_id"] != RESOURCE or uncertain[0]["observed_release"] is not False
            or uncertain[0]["expired"] is not True or len(released) != 2
            or any(row["observed_release"] is not True for row in released)):
        raise RuntimeError("BS exact uncertain cleanup boundary required")
    return {"outcome": "BS_UNCERTAIN_CLEANUP_PREFLIGHT_GREEN", "facts": value,
            "sourceReads": 0, "attemptsCreated": 0}


def recover_resource() -> dict:
    preflight()
    recovery = ExpiredResourceRecovery(
        connect=runtime._runtime_connect_factory(),
        driver=CleanupOnlyOciDriver(OciDriver(context="colima-aos-extension")),
    )
    state = recovery.run_one(org_id="org-org", project_id="dev-project", resource_id=RESOURCE)
    if state != "released":
        raise RuntimeError("BS uncertain resource did not become released")
    connect = runtime._runtime_connect_factory()
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        value = facts(conn)
    if any(row["cleanup_state"] != "released" or row["observed_release"] is not True
           for row in value["resources"]):
        raise RuntimeError("BS all resources released readback required")
    return {"outcome": "BS_UNCERTAIN_RESOURCE_RELEASED", "resourceId": RESOURCE,
            "state": state, "facts": value}


def settle_preparation() -> dict:
    connect = runtime._runtime_connect_factory()
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        before = facts(conn)
        if before["operation"] != {"kind": "runtime-apply", "phase": "succeeded",
                "status": "needs_attention", "revision": 21,
                "failure_code": "RESOURCE_CLEANUP_UNCERTAIN"}:
            raise RuntimeError("BS committed cleanup CAS boundary differs")
        if any(row["cleanup_state"] != "released" or row["observed_release"] is not True
               for row in before["resources"]):
            raise RuntimeError("BS released resources required before settlement")
        result = settle_committed_cleanup(conn, org_id="org-org", project_id="dev-project",
                                          operation_id=OPERATION, expected_revision=21)
    if (str(result.operation_id), result.status, result.revision) != (OPERATION, "failed", 22):
        raise RuntimeError("BS committed cleanup settlement differs")
    return {"outcome": "BS_COMMITTED_PREPARATION_RELEASED", "operationId": OPERATION,
            "status": result.status, "revision": result.revision,
            "failureCode": "PREPARED_RUNTIME_RELEASED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "recover-resource", "settle-preparation"))
    args = parser.parse_args()
    action = {"preflight": preflight, "recover-resource": recover_resource,
              "settle-preparation": settle_preparation}[args.action]
    print(json.dumps(action(), ensure_ascii=False, default=str, indent=2))
