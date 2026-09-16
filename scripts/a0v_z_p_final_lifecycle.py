#!/usr/bin/env python3
"""Finish P shrink, nine-route detach and formal uninstall with fixed authorities."""
from __future__ import annotations

import argparse
import json
import os

import a0v_o_recovery as recovery
import a0v_p_successor_business as current
from a0v_p_product_window import policy_profile
from a0v_qyh_current_product_event_first_chain import _approve, freeze, freeze_or_match


STATE = current.STATE.parent / "final-lifecycle-v7"
PREFIX = "a0v-qyh-p-final-lifecycle-20260917-v7"
ACTIONS = ("preflight", "approve-event-shrink", "event-shrink", "request-disable",
           "process-disable", "uninstall", "audit")


def _connect():
    from a0v_formal_text_model_renewal import database_connect
    return database_connect("aos_meta_head")


def _profile():
    return recovery.current()


def _load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def _installation():
    return _profile().observe_installation(current.P_ID)


def _database(phase: str, operation_id: str | None = None) -> dict:
    if phase not in {"fenced", "shrunk", "accepted", "detached", "uninstalled"}:
        raise ValueError("fixed P final lifecycle phase required")
    with _connect()() as conn:
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,operation_fence,revision,
          cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (current.GROUP,)).fetchall()]
        runtime = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,
          desired_state,observed_state FROM extension_runtime_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s AND generation=%s""",
          (current.P_ID, current.P_GENERATION)).fetchone()
        resources = dict(conn.execute("""SELECT count(*) total,count(*) FILTER
          (WHERE cleanup_state='released' AND observed_release) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
          AND generation=%s""", (current.P_GENERATION,)).fetchone())
        policy = conn.execute("""SELECT revision,enabled FROM automation_schedule_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s
          AND policy_revision=11""", (policy_profile().POLICY,)).fetchone()
        safety = dict(conn.execute("""SELECT
          (SELECT count(*) FROM automation_occurrence WHERE org_id='org-org' AND project_id='dev-project'
            AND installation_id=%s AND generation=%s AND execution_epoch=3 AND status='cancelled') cancelled,
          (SELECT count(*) FROM ecommerce_unaccepted_analysis_closure_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key LIKE
              'a0v-qyh-p-policy11-retirement-20260917-v6-close-%%') closures,
          (SELECT count(*) FROM ecommerce_growth_runtime_command_receipt r JOIN automation_occurrence o
            ON r.org_id=o.org_id AND r.project_id=o.project_id
            AND r.idempotency_key=coalesce((SELECT a.target_idempotency_key
              FROM automation_occurrence_dispatch_attempt a WHERE a.org_id=o.org_id
              AND a.project_id=o.project_id AND a.occurrence_id=o.occurrence_id),
              'automation-occurrence:'||o.occurrence_id::text)
            WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.installation_id=%s
              AND o.generation=%s AND r.operation_id='ecommerce_growth_analysis_advance') target_receipts,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary""",
          (current.P_ID, current.P_GENERATION, current.P_ID, current.P_GENERATION)).fetchone())
        lifecycle = {"operations": 0, "receipts": 0, "phases": []}
        operation = None
        if operation_id is not None:
            operation = conn.execute("""SELECT operation_id::text,kind,status,phase,revision,
              expected_binding_revision,requested_by FROM extension_runtime_operation
              WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
              (operation_id,)).fetchone()
            phases = [row["phase"] for row in conn.execute("""SELECT phase FROM
              extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
              AND runtime_operation_id=%s ORDER BY created_at""", (operation_id,)).fetchall()]
            lifecycle = {"operations": conn.execute("""SELECT count(*) n FROM
              extension_dispatch_lifecycle_operation WHERE org_id='org-org' AND project_id='dev-project'
              AND runtime_operation_id=%s""", (operation_id,)).fetchone()["n"],
              "receipts": len(phases), "phases": phases}
    if (runtime is None or resources != {"total": 3, "released": 3}
            or policy is None or dict(policy) != {"revision": 2, "enabled": False}
            or safety != {"cancelled": 65, "closures": 65, "target_receipts": 0, "canary": 0}):
        raise ValueError("P final lifecycle safety authority differs")
    if phase in {"fenced", "shrunk", "accepted"}:
        expected_runtime = {"revision": 7, "execution_epoch": 4, "enabled": False,
            "operation_fence": True, "desired_state": "enabled", "observed_state": "unknown"}
    elif phase == "detached":
        expected_runtime = {"revision": 9, "execution_epoch": 5, "enabled": False,
            "operation_fence": True, "desired_state": "disabled", "observed_state": "unknown"}
    else:
        expected_runtime = {"revision": 10, "execution_epoch": 5, "enabled": False,
            "operation_fence": True, "desired_state": "uninstalled", "observed_state": "stopped"}
    if dict(runtime) != expected_runtime:
        raise ValueError("P final lifecycle runtime differs")
    if phase == "fenced":
        if len(routes) != 10 or any(row["handler_kind"] != "extension"
                or row["installation_id"] != current.P_ID or row["generation"] != current.P_GENERATION
                or row["execution_epoch"] != 3 or row["cutover_group_revision"] != 50 for row in routes):
            raise ValueError("exact fenced P route group required")
        event = next(row for row in routes if row["operation_id"] == "ecommerce_growth_event_control")
        if event["operation_fence"] is not True or any(
                row["operation_fence"] for row in routes if row is not event):
            raise ValueError("only event route may be fenced")
    elif phase in {"shrunk", "accepted"}:
        if len(routes) != 9 or any(row["handler_kind"] != "extension"
                or row["installation_id"] != current.P_ID or row["generation"] != current.P_GENERATION
                or row["execution_epoch"] != 3 or row["operation_fence"] is not False
                or row["revision"] != 27 or row["cutover_group_revision"] != 51 for row in routes):
            raise ValueError("exact shrunk P route group required")
    else:
        if len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                or row["generation"] is not None or row["execution_epoch"] is not None
                or row["operation_fence"] is not True or row["revision"] != 29
                or row["cutover_group_revision"] != 53 for row in routes):
            raise ValueError("exact detached P route group required")
    if phase == "accepted":
        if (operation is None or operation["kind"] != "disable" or operation["status"] != "accepted"
                or operation["phase"] != "accepted" or operation["revision"] != 1
                or operation["expected_binding_revision"] != 7 or lifecycle != {
                    "operations": 0, "receipts": 0, "phases": []}):
            raise ValueError("exact accepted P disable required")
    if phase in {"detached", "uninstalled"}:
        if (operation is None or operation["kind"] != "disable" or operation["status"] != "succeeded"
                or operation["phase"] != "succeeded" or lifecycle != {
                    "operations": 1, "receipts": 2, "phases": ["fence", "detach"]}):
            raise ValueError("exact succeeded P disable lifecycle required")
    return {"phase": phase, "runtime": dict(runtime), "resourceCounts": resources,
            "routeCount": len(routes), "groupRevision": routes[0]["cutover_group_revision"],
            "safety": safety, "operation": None if operation is None else dict(operation),
            "lifecycle": lifecycle}


def preflight() -> dict:
    snapshot = _installation()
    head = snapshot["head"]
    if (head["state"] != "active" or head["etag_version"] != 5
            or str(head["installation_id"]) != current.P_ID or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact active P installation required")
    return {"outcome": "P_FINAL_LIFECYCLE_PREFLIGHT_GREEN",
            "database": _database("fenced"), "installationState": "active", "externalEffects": 0}


def _shrink_request() -> dict:
    return {"schemaVersion": "aos.ecommerce.event-control-dispatch/v1", "phase": "shrink",
        "installationRef": {"installationId": current.P_ID, "revision": 5,
            "lockHash": current.LOCK, "overlayRevision": "a0v-canonical-ecommerce-v1"},
        "generation": current.P_GENERATION, "executionEpoch": 3, "runtimeRevision": 7,
        "cutoverGroupId": current.GROUP, "expectedGroupRevision": 50,
        "caseId": policy_profile().CASE, "schedulePolicyId": policy_profile().POLICY,
        "idempotencyKey": PREFIX + "-event-shrink"}


def _approve_main(payload: dict):
    from psycopg.conninfo import make_conninfo
    with _connect()() as conn:
        parameters = conn.info.get_parameters()
        parameters["password"] = conn.info.password
    previous = os.environ.get("AOS_DATABASE_URL")
    os.environ["AOS_DATABASE_URL"] = make_conninfo(**parameters)
    try:
        return _approve("ecommerce_growth_event_dispatch", payload, PREFIX + "-shrink-approval")
    finally:
        if previous is None:
            os.environ.pop("AOS_DATABASE_URL", None)
        else:
            os.environ["AOS_DATABASE_URL"] = previous


def approve_event_shrink() -> dict:
    _load("preflight")
    _database("fenced")
    request = _shrink_request()
    payload = {"caseId": policy_profile().CASE, "schedulePolicyId": policy_profile().POLICY,
               "dispatchIntent": request}
    freeze_or_match(STATE / "approve-event-shrink-intent.json", payload)
    bundle, ref = _approve_main(payload)
    return {"outcome": "P_EVENT_SHRINK_APPROVED", "request": request,
            "approvalRef": ref, "proposalId": bundle.proposal.id}


def event_shrink() -> dict:
    approved = _load("approve-event-shrink")
    if approved["request"] != _shrink_request():
        raise ValueError("P event shrink approval drifted")
    from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
    from aos_api.tenant_scope import TenantScope
    request = EventControlDispatchRequest.model_validate(
        {**approved["request"], "approvalRef": approved["approvalRef"]})
    freeze_or_match(STATE / "event-shrink-intent.json", request.wire())
    scope = TenantScope("org-org", "dev-project")
    receipt = current.setup().pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(
        scope=scope, request=request, actor=current.ACTOR)
    return {"outcome": "P_RELEASED_EVENT_SHRINK_GREEN", "receipt": receipt,
            "database": _database("shrunk")}


def request_disable() -> dict:
    _load("event-shrink")
    _database("shrunk")
    profile = _profile()
    command = profile.require_released_owner_settlement(_installation())
    intent = {"installationId": current.P_ID, **command,
              "idempotencyKey": PREFIX + "-settle-released"}
    freeze_or_match(STATE / "request-disable-intent.json", intent)
    activation, _store, _lifecycle, service, _dependent = profile._setup_runtime_plane()
    receipt = service.request(**profile.SCOPE, installation_id=current.P_ID,
        actor=activation.ACTOR, roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"], if_match='"5"', target={
            "generation": command["generation"], "bindingRevision": command["bindingRevision"]})
    operation_id = receipt.response_json["operationId"]
    return {"outcome": "P_RELEASED_DISABLE_ACCEPTED", "operationId": operation_id,
            "receipt": receipt.response_json, "replayed": receipt.replayed,
            "database": _database("accepted", operation_id)}


def process_disable() -> dict:
    requested = _load("request-disable")
    operation_id = requested["operationId"]
    _database("accepted", operation_id)
    profile = _profile()
    current.setup()
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    activation, store, _lifecycle, _service, _dependent = profile._setup_runtime_plane()
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent())
    scope = TenantScope("org-org", "dev-project")
    with consumer._connection(dict(org_id=scope.org_id, project_id=scope.project_id)) as conn:
        lease = consumer.outbox.claim(conn, org_id=scope.org_id, project_id=scope.project_id,
            operation_kind="disable", installation_id=current.P_ID)
    if lease is None or str(lease.operation_id) != operation_id:
        raise ValueError("exact P disable delivery required")
    freeze_or_match(STATE / "process-disable-intent.json", {
        "operationId": operation_id, "eventId": str(lease.event_id), "resendDisable": False})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(current.P_ID)))
    if (str(delivery.operation_id) != operation_id or delivery.operation_status != "succeeded"
            or delivery.delivery_status != "acknowledged"):
        raise ValueError("P disable delivery did not settle")
    return {"outcome": "P_NINE_ROUTES_DETACHED", "operationId": operation_id,
            "deliveryStatus": delivery.delivery_status, "resendDisable": False,
            "database": _database("detached", operation_id)}


def uninstall() -> dict:
    processed = _load("process-disable")
    operation_id = processed["operationId"]
    intent = {"installationId": current.P_ID, "etag": 5, "generation": current.P_GENERATION,
              "bindingRevision": 9, "runtimeOperationId": operation_id,
              "idempotencyKey": PREFIX + "-uninstall"}
    intent_path = STATE / "uninstall-intent.json"
    existed = intent_path.exists()
    _database("uninstalled" if existed else "detached", operation_id)
    snapshot = _installation()
    expected_head = ("uninstalled", 6) if existed else ("active", 5)
    if (snapshot["head"]["state"], snapshot["head"]["etag_version"]) != expected_head:
        raise ValueError("exact current P uninstall state required")
    freeze_or_match(intent_path, intent)
    profile = _profile()
    legacy = profile._load("a0v_ecommerce_invalid_baseline_uninstall")
    store, service = legacy._build(profile._installation_connection,
                                   profile.TRUST_STATE / "signing/trust-roots.json")
    if existed:
        with _connect()() as conn:
            row = conn.execute("""SELECT operation,status_code,response_json,response_etag
              FROM bundle_installation_command WHERE org_id='org-org' AND project_id='dev-project'
              AND idempotency_key=%s""", (intent["idempotencyKey"],)).fetchone()
        if (row is None or row["operation"] != "bundle_installations.uninstall"
                or row["status_code"] != 200 or row["response_etag"] != '"6"'
                or row["response_json"].get("installationId") != current.P_ID
                or row["response_json"].get("state") != "uninstalled"
                or row["response_json"].get("etagVersion") != 6):
            raise ValueError("exact committed P uninstall Receipt required for readback")
        receipt_payload = dict(row)
        replayed = True
    else:
        from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
        receipt = service.uninstall(**profile.SCOPE, installation_id=current.P_ID,
            request=UninstallInstallationRequest(
                reason="P failed natural window is closed, released and detached before clean successor"),
            actor=current.ACTOR, roles=["admin"], markings=[],
            idempotency_key=intent["idempotencyKey"], if_match='"5"')
        receipt_payload = {"status_code": receipt.status_code, "response_json": receipt.response_json,
                           "response_etag": receipt.response_etag}
        replayed = receipt.replayed
    record = store.get_installation(**profile.SCOPE, installation_id=current.P_ID)
    if record.state != "uninstalled" or record.active_revision is not None or record.etag_version != 6:
        raise ValueError("P uninstall readback differs")
    return {"outcome": "P_FORMALLY_UNINSTALLED", "receipt": receipt_payload,
            "replayed": replayed, "installationState": record.state,
            "installationEtag": record.etag_version,
            "database": _database("uninstalled", operation_id)}


def audit() -> dict:
    uninstalled = _load("uninstall")
    state = _database("uninstalled", uninstalled["database"]["operation"]["operation_id"])
    snapshot = _installation()
    if (snapshot["head"]["state"] != "uninstalled" or snapshot["head"]["etag_version"] != 6
            or snapshot["head"].get("active_revision") is not None):
        raise ValueError("formal P uninstall audit differs")
    return {"outcome": "P_FINAL_LIFECYCLE_GREEN", "installationState": "uninstalled",
            "installationEtag": 6, "database": state, "externalEffects": 0}


def run(action: str) -> dict:
    if action not in ACTIONS:
        raise ValueError("unsupported P final lifecycle action")
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
