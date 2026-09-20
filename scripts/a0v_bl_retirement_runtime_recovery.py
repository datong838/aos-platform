#!/usr/bin/env python3
"""Recover BL retirement through original Owners without the removed credential file."""
from __future__ import annotations

import argparse
import json
from uuid import UUID

import a0v_bl_expired_attempt_recovery as runtime
import a0v_bl_terminal_retirement as bl
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.disable_service import RuntimeDisableService
from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
from aos_api.extension_runtime.committed_cleanup import settle_committed_cleanup
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallCleanupExecutor
from aos_api.tenant_scope import TenantScope


def request_disable() -> dict:
    if bl.retirement.snapshot("active").get("phase") != "active":
        raise RuntimeError("BL active retirement boundary required")
    intent_path = bl.retirement.STATE / "request-disable-intent.json"
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    expected = {
        "installationId": bl.retirement.AQ_ID,
        "etag": 5,
        "generation": bl.retirement.GENERATION,
        "bindingRevision": 6,
        "idempotencyKey": bl.retirement.PREFIX + "-disable",
    }
    if intent != expected:
        raise RuntimeError("BL immutable disable intent differs")
    connect = runtime._runtime_connect_factory()
    store = PostgresInstallationStore(connect_factory=connect)
    reader = InstallationService(
        store=store, composition_store=PostgresCompositionStore(connect_factory=connect),
        revalidator=None,
    )
    service = RuntimeDisableService(
        installation_store=store, installation_reader=reader,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        dependent=EcommerceGrowthDisableDependent(),
    )
    actor = "a0v-ecommerce-growth-1.4-runtime-owner"
    receipt = service.request(
        org_id="org-org", project_id="dev-project", installation_id=bl.retirement.AQ_ID,
        actor=actor, roles=frozenset({"admin"}), markings=frozenset(),
        idempotency_key=intent["idempotencyKey"], if_match='"5"',
        target={"generation": bl.retirement.GENERATION, "bindingRevision": 6},
    )
    operation_id = receipt.response_json["operationId"]
    result = {
        "outcome": "BL_TERMINAL_DISABLE_ACCEPTED", "operationId": operation_id,
        "receipt": receipt.response_json, "replayed": receipt.replayed,
        "state": bl.retirement.snapshot("accepted", operation_id),
    }
    output = bl.retirement.STATE / "request-disable-result.json"
    if output.exists():
        if json.loads(output.read_text(encoding="utf-8")) != result:
            raise RuntimeError("BL request-disable result differs")
    else:
        bl.retirement.freeze(output, result)
    return result


def _core_snapshot(operation_id: str) -> dict:
    with bl.retirement.connect()() as conn:
        operation = dict(conn.execute("""SELECT operation_id::text,status,phase,revision
          FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
          AND operation_id=%s""", (operation_id,)).fetchone())
        binding = dict(conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,
          desired_state,observed_state FROM extension_runtime_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND generation=%s""", (bl.retirement.AQ_ID, bl.retirement.GENERATION)).fetchone())
        routes = dict(conn.execute("""SELECT count(*) total,
          count(*) FILTER (WHERE handler_kind='legacy' AND installation_id IS NULL
            AND generation IS NULL AND execution_epoch IS NULL AND operation_fence
            AND revision=164 AND cutover_group_revision=191) detached
          FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s""", (bl.retirement.GROUP,)).fetchone())
        resources = dict(conn.execute("""SELECT count(*) total,
          count(*) FILTER (WHERE cleanup_state='pending' AND observed_release IS FALSE) pending,
          count(*) FILTER (WHERE cleanup_state='released' AND observed_release IS TRUE) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
          AND generation=%s""", (bl.retirement.GENERATION,)).fetchone())
        phases = [row["phase"] for row in conn.execute("""SELECT phase
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (operation_id,)).fetchall()]
    value = {"operation": operation, "binding": binding, "routes": routes,
             "resources": resources, "phases": phases}
    expected = {
        "operation": {"operation_id": operation_id, "status": "succeeded", "phase": "succeeded", "revision": 6},
        "binding": {"revision": 8, "execution_epoch": 4, "enabled": False,
                    "operation_fence": True, "desired_state": "disabled", "observed_state": "unknown"},
        "routes": {"total": 9, "detached": 9},
        "resources": {"total": 3, "pending": 3, "released": 0},
        "phases": ["fence", "detach"],
    }
    if value != expected:
        raise RuntimeError("BL disable core readback differs")
    return value


def process_disable_core() -> dict:
    request = bl.retirement.load("request-disable")
    operation_id = request["operationId"]
    try:
        completed = _core_snapshot(operation_id)
    except RuntimeError:
        completed = None
    if completed is not None:
        claimed_by_host = bl.retirement.recover_completed_intent(
            bl.retirement.STATE / "process-disable-intent.json", operation_id
        )
        result = {"outcome": "BL_DISABLE_CORE_COMMITTED", "operationId": operation_id,
                  "claimedByHost": claimed_by_host, "resendDisable": False,
                  "recoveredAfterCommit": True, "state": completed}
        output = bl.retirement.STATE / "process-disable-core-result.json"
        if not output.exists():
            bl.retirement.freeze(output, result)
        return result
    bl.retirement.snapshot("accepted", operation_id)
    connect = runtime._runtime_connect_factory()
    store = PostgresInstallationStore(connect_factory=connect)
    consumer = RuntimeDisableConsumer(
        connect=connect, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent(),
    )
    scope = TenantScope(org_id="org-org", project_id="dev-project")
    with consumer._connection({"org_id": scope.org_id, "project_id": scope.project_id}) as conn:
        lease = consumer.outbox.claim(conn, org_id=scope.org_id, project_id=scope.project_id,
                                      operation_kind="disable", installation_id=bl.retirement.AQ_ID)
    if lease is None or str(lease.operation_id) != operation_id:
        raise RuntimeError("BL exact disable delivery unavailable")
    bl.retirement.freeze_or_match(
        bl.retirement.STATE / "process-disable-intent.json",
        {"operationId": operation_id, "eventId": str(lease.event_id), "resendDisable": False},
    )
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(bl.retirement.AQ_ID)))
    if (str(delivery.operation_id), delivery.operation_status, delivery.delivery_status) != (
            operation_id, "succeeded", "acknowledged"):
        raise RuntimeError("BL disable delivery did not settle")
    result = {"outcome": "BL_DISABLE_CORE_COMMITTED", "operationId": operation_id,
              "claimedByHost": False, "resendDisable": False,
              "deliveryStatus": delivery.delivery_status, "state": _core_snapshot(operation_id)}
    output = bl.retirement.STATE / "process-disable-core-result.json"
    if output.exists():
        if json.loads(output.read_text(encoding="utf-8")) != result:
            raise RuntimeError("BL disable core result differs")
    else:
        bl.retirement.freeze(output, result)
    return result


def release_resources() -> dict:
    core_path = bl.retirement.STATE / "process-disable-core-result.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    if core.get("outcome") != "BL_DISABLE_CORE_COMMITTED":
        raise RuntimeError("BL committed disable core required")
    executor = RuntimeUninstallCleanupExecutor(
        connect=runtime._runtime_connect_factory(),
        driver=CleanupOnlyOciDriver(OciDriver(context="colima-aos-extension")),
    )
    page = executor.run_batch(
        org_id="org-org", project_id="dev-project",
        installation_id=bl.retirement.AQ_ID, generation=bl.retirement.GENERATION,
        limit=3,
    )
    results = [(str(resource_id), state) for resource_id, state in page.results]
    if len(results) != 3 or any(state != "released" for _, state in results):
        raise RuntimeError("BL exact resource release differs")
    operation_id = core["operationId"]
    detached = bl.retirement.snapshot("detached", operation_id)
    result = {"outcome": "BL_RESOURCES_RELEASED", "operationId": operation_id,
              "results": results, "state": detached}
    output = bl.retirement.STATE / "release-resources-result.json"
    if not output.exists():
        bl.retirement.freeze(output, result)
    return result


def confirm_released() -> dict:
    recovery = ExpiredResourceRecovery(
        connect=runtime._runtime_connect_factory(),
        driver=CleanupOnlyOciDriver(OciDriver(context="colima-aos-extension")),
    )
    target = {"38a24392-5f03-45ea-bc0d-26819b9ac939",
              "64957386-6563-4f90-b3a9-da7a3b1cc166",
              "837baf63-7869-449a-b502-c53a389391c0"}
    observed = {
        resource_id: recovery.run_one(org_id="org-org", project_id="dev-project",
                                      resource_id=resource_id)
        for resource_id in sorted(target)
    }
    if observed != {resource_id: "released" for resource_id in target}:
        raise RuntimeError("BL exact expired resource confirmation differs")
    core = json.loads((bl.retirement.STATE / "process-disable-core-result.json").read_text(encoding="utf-8"))
    operation_id = core["operationId"]
    result = {"outcome": "BL_RESOURCES_RELEASE_CONFIRMED", "operationId": operation_id,
              "results": observed, "state": bl.retirement.snapshot("detached", operation_id)}
    output = bl.retirement.STATE / "confirm-released-result.json"
    if not output.exists():
        bl.retirement.freeze(output, result)
    return result


def settle_preparation() -> dict:
    operation_id = "319f1b2b-1cdf-49de-bc0c-b9779f018200"
    connect = runtime._runtime_connect_factory()
    with consumer_connection(connect, {"org_id": "org-org", "project_id": "dev-project"}) as conn:
        row = conn.execute("""SELECT kind,phase,status,revision,failure_code
          FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
          AND operation_id=%s""", (operation_id,)).fetchone()
        if dict(row) != {"kind": "runtime-apply", "phase": "succeeded", "status": "needs_attention",
                         "revision": 64, "failure_code": "RESOURCE_CLEANUP_UNCERTAIN"}:
            raise RuntimeError("BL exact uncertain preparation differs")
        result = settle_committed_cleanup(
            conn, org_id="org-org", project_id="dev-project",
            operation_id=operation_id, expected_revision=64,
        )
    if (str(result.operation_id), result.status, result.revision) != (operation_id, "failed", 65):
        raise RuntimeError("BL committed cleanup settlement differs")
    return {"outcome": "BL_COMMITTED_PREPARATION_RELEASED", "operationId": operation_id,
            "status": result.status, "revision": result.revision,
            "failureCode": "PREPARED_RUNTIME_RELEASED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("request-disable", "process-disable-core", "release-resources",
                                           "confirm-released", "settle-preparation"))
    args = parser.parse_args()
    action = {"request-disable": request_disable, "process-disable-core": process_disable_core,
              "release-resources": release_resources, "confirm-released": confirm_released,
              "settle-preparation": settle_preparation}[args.action]
    print(json.dumps(action(), ensure_ascii=False, default=str, indent=2))
