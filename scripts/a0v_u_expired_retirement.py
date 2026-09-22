#!/usr/bin/env python3
"""Detach expired U through the original disable Owner; never alter snapshot runs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-v/retire-u"
U_ID = "277fe01c-ece7-4c8f-9500-fc1ba0d5f050"
GENERATION = "f576ea28-7c2b-4032-8b4c-9d196df6228e"
LOCK = "sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
DEFINITION = "cb0dba8c-803f-5caf-8011-b763d349f2ba"
PREFIX = "a0v-qyh-expired-u-retirement-20260917-v1"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
ACTIONS = ("preflight", "request-disable", "process-disable", "audit")


def freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("immutable U retirement intent differs")
        return
    freeze(path, value)


def load(name: str) -> dict[str, Any]:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def connect():
    sys.path.insert(0, str(ROOT / "scripts"))
    from a0v_formal_text_model_renewal import database_connect
    return database_connect("aos_meta_head")


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
    return value


def setup():
    import a0v_u_successor_business as current
    return current.setup()


def snapshot(phase: str, operation_id: str | None = None) -> dict[str, Any]:
    if phase not in {"released", "accepted", "detached"}:
        raise ValueError("fixed U retirement phase required")
    detached = phase == "detached"
    with connect()() as conn:
        head = conn.execute("""SELECT i.installation_id::text,i.etag_version,r.state,r.lock_hash,r.overlay_revision
          FROM bundle_installation i JOIN bundle_installation_revision r
            ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
               (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""", (U_ID,)).fetchone()
        runtime = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,desired_state,observed_state
          FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project'
           AND installation_id=%s AND generation=%s""", (U_ID, GENERATION)).fetchone()
        resources = dict(conn.execute("""SELECT count(*) total,count(*) FILTER
          (WHERE cleanup_state='released' AND observed_release) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
           AND generation=%s""", (GENERATION,)).fetchone())
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,operation_fence,revision,
          cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (GROUP,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          (DEFINITION,)).fetchone()
        safety = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
            AND installation_id=%s AND status NOT IN ('succeeded','failed','cancelled')) runtime_pending,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary""", (U_ID, GENERATION, U_ID)).fetchone())
        operation = None
        lifecycle = {"operations": 0, "receipts": 0, "phases": []}
        if operation_id is not None:
            operation = conn.execute("""SELECT operation_id::text,kind,status,phase,revision,
              expected_binding_revision FROM extension_runtime_operation WHERE org_id='org-org'
              AND project_id='dev-project' AND operation_id=%s""", (operation_id,)).fetchone()
            phases = [row["phase"] for row in conn.execute("""SELECT phase
              FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
              AND runtime_operation_id=%s ORDER BY created_at""", (operation_id,)).fetchall()]
            lifecycle = {"operations": conn.execute("""SELECT count(*) n
              FROM extension_dispatch_lifecycle_operation WHERE org_id='org-org' AND project_id='dev-project'
              AND runtime_operation_id=%s""", (operation_id,)).fetchone()["n"],
              "receipts": len(phases), "phases": phases}
    expected_head = {"installation_id": U_ID, "etag_version": 5, "state": "active",
                     "lock_hash": LOCK, "overlay_revision": "a0v-canonical-ecommerce-v1"}
    expected_runtime = ({"revision": 9, "execution_epoch": 5, "enabled": False,
                         "operation_fence": True, "desired_state": "disabled", "observed_state": "unknown"}
                        if detached else
                        {"revision": 7, "execution_epoch": 4, "enabled": False,
                         "operation_fence": True, "desired_state": "enabled", "observed_state": "unknown"})
    expected_safety = {"running": 0, "unresolved": 0,
                       "runtime_pending": 0 if phase != "accepted" else 1, "canary": 0}
    if (head is None or dict(head) != expected_head or runtime is None or dict(runtime) != expected_runtime
            or resources != {"total": 3, "released": 3} or len(routes) != 9
            or definition is None or dict(definition) != {"revision": 4, "state": "disabled"}
            or safety != expected_safety):
        raise ValueError("exact released U retirement authority differs")
    if detached:
        if any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
               or row["generation"] is not None or row["execution_epoch"] is not None
               or row["operation_fence"] is not True or row["revision"] != 38
               or row["cutover_group_revision"] != 65 for row in routes):
            raise ValueError("exact detached U routes required")
    elif any(row["handler_kind"] != "extension" or row["installation_id"] != U_ID
             or row["generation"] != GENERATION or row["execution_epoch"] != 3
             or row["operation_fence"] is not False or row["revision"] != 36
             or row["cutover_group_revision"] != 63 for row in routes):
        raise ValueError("exact attached U routes required")
    if phase == "accepted" and (operation is None or operation["kind"] != "disable"
            or operation["status"] != "accepted" or operation["phase"] != "accepted"
            or operation["expected_binding_revision"] != 7
            or lifecycle != {"operations": 0, "receipts": 0, "phases": []}):
        raise ValueError("exact accepted U disable required")
    if detached and (operation is None or operation["status"] != "succeeded"
            or operation["phase"] != "succeeded"
            or lifecycle != {"operations": 1, "receipts": 2, "phases": ["fence", "detach"]}):
        raise ValueError("exact detached U lifecycle required")
    return {"phase": phase, "runtime": dict(runtime), "resources": resources,
            "routeCount": 9, "groupRevision": 65 if detached else 63,
            "definition": dict(definition), "safety": safety,
            "operation": None if operation is None else dict(operation), "lifecycle": lifecycle}


def preflight() -> dict[str, Any]:
    return {"outcome": "U_EXPIRED_RETIREMENT_PREFLIGHT_GREEN",
            "state": snapshot("released"), "externalEffects": 0}


def request_disable() -> dict[str, Any]:
    load("preflight")
    snapshot("released")
    current = profile()
    command = current.require_released_owner_settlement(current.observe_installation(U_ID))
    intent = {"installationId": U_ID, **command,
              "idempotencyKey": PREFIX + "-settle-released"}
    freeze_or_match(STATE / "request-disable-intent.json", intent)
    activation, _store, _lifecycle, service, _dependent = current._setup_runtime_plane()
    receipt = service.request(**SCOPE, installation_id=U_ID, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"], if_match='"5"',
        target={"generation": GENERATION, "bindingRevision": command["bindingRevision"]})
    operation_id = receipt.response_json["operationId"]
    return {"outcome": "U_EXPIRED_DISABLE_ACCEPTED", "operationId": operation_id,
            "receipt": receipt.response_json, "replayed": receipt.replayed,
            "state": snapshot("accepted", operation_id)}


def process_disable() -> dict[str, Any]:
    operation_id = load("request-disable")["operationId"]
    try:
        completed = snapshot("detached", operation_id)
    except ValueError:
        completed = None
    if completed is not None:
        freeze_or_match(STATE / "process-disable-intent.json",
                        {"operationId": operation_id, "claimedByHost": True, "resendDisable": False})
        return {"outcome": "U_NINE_ROUTES_DETACHED", "operationId": operation_id,
                "claimedByHost": True, "resendDisable": False, "state": completed}
    snapshot("accepted", operation_id)
    setup()
    current = profile()
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    _activation, store, _lifecycle, _service, _dependent = current._setup_runtime_plane()
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent())
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable", installation_id=U_ID)
    if lease is None or str(lease.operation_id) != operation_id:
        raise ValueError("exact U disable delivery required")
    freeze_or_match(STATE / "process-disable-intent.json",
                    {"operationId": operation_id, "eventId": str(lease.event_id), "resendDisable": False})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(U_ID)))
    if (str(delivery.operation_id) != operation_id or delivery.operation_status != "succeeded"
            or delivery.delivery_status != "acknowledged"):
        raise ValueError("U disable delivery did not settle")
    return {"outcome": "U_NINE_ROUTES_DETACHED", "operationId": operation_id,
            "claimedByHost": False, "resendDisable": False,
            "deliveryStatus": delivery.delivery_status, "state": snapshot("detached", operation_id)}


def audit() -> dict[str, Any]:
    operation_id = load("process-disable")["operationId"]
    return {"outcome": "U_EXPIRED_RETIREMENT_GREEN",
            "state": snapshot("detached", operation_id), "externalEffects": 0}


def run(action: str) -> dict[str, Any]:
    if action not in ACTIONS:
        raise ValueError("unsupported U retirement action")
    result = globals()[action.replace("-", "_")]()
    output = STATE / f"{action}-result.json"
    if not output.exists():
        freeze(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))
