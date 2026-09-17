#!/usr/bin/env python3
"""Retire released S through the original disable Owner and route lifecycle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/released-s-retirement"
S_ID = "77b8e5c2-db96-4d55-a808-1b62e00163d2"
GENERATION = "e621100a-baea-440f-9075-ae8a5290845a"
LOCK = "sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
PREFIX = "a0v-qyh-released-s-retirement-20260917-v1"
DEFINITION = "ece2c4cb-743e-56ab-b1d7-41055e606136"
OCCURRENCES = (
    "3c927751-b91a-53d0-8a42-7c5223ea109d",
    "34733f17-f1ce-582d-b1b6-585a96aee2ff",
)
ACTIONS = ("preflight", "request-disable", "process-disable", "audit")


def freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError(f"immutable intent differs: {path.name}")
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


def setup():
    sys.path.insert(0, str(ROOT / "scripts"))
    import a0v_s_successor_business as current
    return current.setup()


def _profile():
    import a0v_ecommerce_current_reinstall as profile
    profile.BUNDLE_ROOT = (ROOT.parent /
        ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete")
    return profile


def snapshot(phase: str, operation_id: str | None = None) -> dict[str, Any]:
    rules = {
        "released": {"runtime": (7, 4, "enabled"), "group": 60, "routes": "extension"},
        "accepted": {"runtime": (7, 4, "enabled"), "group": 60, "routes": "extension"},
        "detached": {"runtime": (9, 5, "disabled"), "group": 62, "routes": "legacy"},
    }
    if phase not in rules:
        raise ValueError("fixed S retirement phase required")
    rule = rules[phase]
    with connect()() as conn:
        head = conn.execute("""SELECT i.installation_id::text,i.etag_version,r.state,r.lock_hash,r.overlay_revision
          FROM bundle_installation i JOIN bundle_installation_revision r
            ON r.installation_pk=i.installation_pk AND r.org_id=i.org_id
           AND r.project_id=i.project_id AND r.revision=i.current_revision
          WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
          (S_ID,)).fetchone()
        runtime = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,desired_state,observed_state
          FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project'
           AND installation_id=%s AND generation=%s""", (S_ID, GENERATION)).fetchone()
        resources = dict(conn.execute("""SELECT count(*) total,count(*) FILTER
          (WHERE cleanup_state='released' AND observed_release) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
           AND generation=%s""", (GENERATION,)).fetchone())
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,operation_fence,revision,
          cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (GROUP,)).fetchall()]
        occurrences = [dict(row) for row in conn.execute("""SELECT occurrence_id::text,status,
          (SELECT a.status FROM automation_occurrence_dispatch_attempt a WHERE a.org_id=o.org_id
           AND a.project_id=o.project_id AND a.occurrence_id=o.occurrence_id) attempt_status
          FROM automation_occurrence o WHERE o.org_id='org-org' AND o.project_id='dev-project'
           AND o.occurrence_id=ANY(%s) ORDER BY occurrence_id""", (list(OCCURRENCES),)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=(h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          (DEFINITION,)).fetchone()
        safety = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project'
            AND policy_id LIKE 'product-event-%%' AND enabled) enabled_event_bindings,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary""", (S_ID, GENERATION)).fetchone())
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
    expected_head = {"installation_id": S_ID, "etag_version": 5, "state": "active",
        "lock_hash": LOCK, "overlay_revision": "a0v-canonical-ecommerce-v1"}
    expected_runtime = {"revision": rule["runtime"][0], "execution_epoch": rule["runtime"][1],
        "enabled": False, "operation_fence": True, "desired_state": rule["runtime"][2],
        "observed_state": "unknown"}
    if (head is None or dict(head) != expected_head or runtime is None or dict(runtime) != expected_runtime
            or resources != {"total": 3, "released": 3} or len(routes) != 9
            or any(row["cutover_group_revision"] != rule["group"] for row in routes)
            or safety != {"running": 0, "unresolved": 0, "enabled_event_bindings": 0, "canary": 0}
            or occurrences != [{"occurrence_id": value, "status": "cancelled",
                                "attempt_status": "closed_unaccepted"}
                               for value in sorted(OCCURRENCES)]
            or definition is None or dict(definition) != {"revision": 9, "state": "disabled"}):
        raise ValueError("exact released S retirement authority differs")
    if rule["routes"] == "extension":
        if any(row["handler_kind"] != "extension" or row["installation_id"] != S_ID
               or row["generation"] != GENERATION or row["execution_epoch"] != 3
               or row["operation_fence"] is not False for row in routes):
            raise ValueError("exact attached S routes required")
    elif any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
             or row["generation"] is not None or row["execution_epoch"] is not None
             or row["operation_fence"] is not True for row in routes):
        raise ValueError("exact detached S routes required")
    if phase == "accepted" and (operation is None or operation["kind"] != "disable"
            or operation["status"] != "accepted" or operation["phase"] != "accepted"
            or operation["expected_binding_revision"] != 7 or lifecycle !=
            {"operations": 0, "receipts": 0, "phases": []}):
        raise ValueError("exact accepted S disable required")
    if phase == "detached" and (operation is None or operation["status"] != "succeeded"
            or operation["phase"] != "succeeded" or lifecycle !=
            {"operations": 1, "receipts": 2, "phases": ["fence", "detach"]}):
        raise ValueError("exact detached S lifecycle required")
    return {"phase": phase, "runtime": dict(runtime), "resources": resources,
        "routeCount": len(routes), "groupRevision": rule["group"], "occurrences": occurrences,
        "definition": dict(definition), "safety": safety,
        "operation": None if operation is None else dict(operation), "lifecycle": lifecycle}


def preflight() -> dict[str, Any]:
    return {"outcome": "S_RELEASED_RETIREMENT_PREFLIGHT_GREEN",
        "state": snapshot("released"), "externalEffects": 0}


def request_disable() -> dict[str, Any]:
    load("preflight")
    snapshot("released")
    profile = _profile()
    current = profile.observe_installation(S_ID)
    command = profile.require_released_owner_settlement(current)
    intent = {"installationId": S_ID, **command,
              "idempotencyKey": PREFIX + "-settle-released"}
    freeze_or_match(STATE / "request-disable-intent.json", intent)
    activation, _store, _lifecycle, service, _dependent = profile._setup_runtime_plane()
    receipt = service.request(**SCOPE, installation_id=S_ID, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"], if_match='"5"',
        target={"generation": GENERATION, "bindingRevision": command["bindingRevision"]})
    operation_id = receipt.response_json["operationId"]
    return {"outcome": "S_RELEASED_DISABLE_ACCEPTED", "operationId": operation_id,
        "receipt": receipt.response_json, "replayed": receipt.replayed,
        "state": snapshot("accepted", operation_id)}


def process_disable() -> dict[str, Any]:
    requested = load("request-disable")
    operation_id = requested["operationId"]
    try:
        completed = snapshot("detached", operation_id)
    except ValueError:
        completed = None
    if completed is not None:
        freeze_or_match(STATE / "process-disable-intent.json",
            {"operationId": operation_id, "claimedByHost": True, "resendDisable": False})
        return {"outcome": "S_NINE_ROUTES_DETACHED", "operationId": operation_id,
            "deliveryStatus": "acknowledged", "claimedByHost": True, "resendDisable": False,
            "state": completed}
    snapshot("accepted", operation_id)
    setup()
    profile = _profile()
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    _activation, store, _lifecycle, _service, _dependent = profile._setup_runtime_plane()
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent())
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable", installation_id=S_ID)
    if lease is None or str(lease.operation_id) != operation_id:
        raise ValueError("exact S disable delivery required")
    freeze_or_match(STATE / "process-disable-intent.json",
        {"operationId": operation_id, "eventId": str(lease.event_id), "resendDisable": False})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(S_ID)))
    if (str(delivery.operation_id) != operation_id or delivery.operation_status != "succeeded"
            or delivery.delivery_status != "acknowledged"):
        raise ValueError("S disable delivery did not settle")
    return {"outcome": "S_NINE_ROUTES_DETACHED", "operationId": operation_id,
        "deliveryStatus": delivery.delivery_status, "claimedByHost": False, "resendDisable": False,
        "state": snapshot("detached", operation_id)}


def audit() -> dict[str, Any]:
    operation_id = load("process-disable")["operationId"]
    return {"outcome": "S_RELEASED_RETIREMENT_GREEN",
        "state": snapshot("detached", operation_id), "externalEffects": 0}


def run(action: str) -> dict[str, Any]:
    if action not in ACTIONS:
        raise ValueError("unsupported S retirement action")
    result = globals()[action.replace("-", "_")]()
    path = STATE / f"{action}-result.json"
    if not path.exists():
        freeze(path, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))
