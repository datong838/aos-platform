"""Retire reboot-released Q through negative controls and formal route detach."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/reboot-q-retirement"
Q_ID = "9c49b383-e04d-41b4-8276-8b8bc6db49a8"
GENERATION = "98aea676-ee71-4d42-a6c8-6634960efe5e"
LOCK = "sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
CASE = "case-qyh-full-store-baseline-20260915"
POLICY = "product-event-qyh-full-store-generation-f-20260916"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
PREFIX = "a0v-q-advisor-reboot-retirement-20260917-v1"
ACTIONS = (
    "preflight",
    "disable-policy12",
    "approve-event-fence",
    "event-fence",
    "approve-event-shrink",
    "event-shrink",
    "request-disable",
    "process-disable",
    "audit",
)


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
    import a0v_q_successor_business as current

    return current.setup()


def snapshot(phase: str, operation_id: str | None = None) -> dict[str, Any]:
    expected = {
        "initial": {"binding": (1, True), "group": 55, "routes": 10, "runtime": (7, 4, "enabled")},
        "disabled": {"binding": (2, False), "group": 55, "routes": 10, "runtime": (7, 4, "enabled")},
        "fenced": {"binding": (2, False), "group": 56, "routes": 10, "runtime": (7, 4, "enabled")},
        "shrunk": {"binding": (2, False), "group": 57, "routes": 9, "runtime": (7, 4, "enabled")},
        "accepted": {"binding": (2, False), "group": 57, "routes": 9, "runtime": (7, 4, "enabled")},
        "detached": {"binding": (2, False), "group": 59, "routes": 9, "runtime": (9, 5, "disabled")},
    }
    if phase not in expected:
        raise ValueError("fixed Q retirement phase required")
    rule = expected[phase]
    with connect()() as conn:
        head = conn.execute(
            """SELECT i.installation_id::text,i.etag_version,r.state,r.lock_hash,r.overlay_revision
                 FROM bundle_installation i JOIN bundle_installation_revision r
                   ON r.installation_pk=i.installation_pk AND r.org_id=i.org_id
                  AND r.project_id=i.project_id AND r.revision=i.current_revision
                WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
            (Q_ID,),
        ).fetchone()
        runtime = conn.execute(
            """SELECT revision,execution_epoch,enabled,operation_fence,desired_state,observed_state
                 FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project'
                  AND installation_id=%s AND generation=%s""",
            (Q_ID, GENERATION),
        ).fetchone()
        resources = dict(
            conn.execute(
                """SELECT count(*) total,count(*) FILTER
                     (WHERE cleanup_state='released' AND observed_release) released
                     FROM extension_runtime_resource_lease WHERE org_id='org-org'
                      AND project_id='dev-project' AND generation=%s""",
                (GENERATION,),
            ).fetchone()
        )
        routes = [
            dict(row)
            for row in conn.execute(
                """SELECT operation_id,handler_kind,installation_id::text,generation::text,
                          execution_epoch,operation_fence,revision,cutover_group_revision
                     FROM extension_operation_dispatch_binding WHERE org_id='org-org'
                      AND project_id='dev-project' AND cutover_group_id=%s ORDER BY operation_id""",
                (GROUP,),
            ).fetchall()
        ]
        binding = conn.execute(
            """SELECT revision,enabled,installation_id::text,generation::text,execution_epoch
                 FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project'
                  AND policy_id=%s AND policy_revision=12""",
            (POLICY,),
        ).fetchone()
        safety = dict(
            conn.execute(
                """SELECT
                  (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
                    AND project_id='dev-project' AND state='running') running,
                  (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
                    USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
                    AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved,
                  (SELECT count(*) FROM automation_occurrence WHERE org_id='org-org' AND project_id='dev-project'
                    AND installation_id=%s AND generation=%s) occurrences,
                  (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
                    AND project_id='dev-project') canary""",
                (Q_ID, GENERATION, Q_ID, GENERATION),
            ).fetchone()
        )
        operation = None
        lifecycle = {"operations": 0, "receipts": 0, "phases": []}
        if operation_id is not None:
            operation = conn.execute(
                """SELECT operation_id::text,kind,status,phase,revision,expected_binding_revision
                     FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
                      AND operation_id=%s""",
                (operation_id,),
            ).fetchone()
            phases = [
                row["phase"]
                for row in conn.execute(
                    """SELECT phase FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org'
                         AND project_id='dev-project' AND runtime_operation_id=%s ORDER BY created_at""",
                    (operation_id,),
                ).fetchall()
            ]
            lifecycle = {
                "operations": conn.execute(
                    """SELECT count(*) n FROM extension_dispatch_lifecycle_operation
                         WHERE org_id='org-org' AND project_id='dev-project' AND runtime_operation_id=%s""",
                    (operation_id,),
                ).fetchone()["n"],
                "receipts": len(phases),
                "phases": phases,
            }
    if (
        head is None
        or dict(head)
        != {
            "installation_id": Q_ID,
            "etag_version": 5,
            "state": "active",
            "lock_hash": LOCK,
            "overlay_revision": "a0v-canonical-ecommerce-v1",
        }
        or resources != {"total": 3, "released": 3}
        or safety != {"running": 0, "unresolved": 0, "occurrences": 0, "canary": 0}
        or binding is None
        or (binding["revision"], binding["enabled"]) != rule["binding"]
        or binding["installation_id"] != Q_ID
        or binding["generation"] != GENERATION
        or binding["execution_epoch"] != 3
    ):
        raise ValueError("exact Q reboot retirement authority differs")
    runtime_expected = {
        "revision": rule["runtime"][0],
        "execution_epoch": rule["runtime"][1],
        "enabled": False,
        "operation_fence": True,
        "desired_state": rule["runtime"][2],
        "observed_state": "unknown",
    }
    if runtime is None or dict(runtime) != runtime_expected:
        raise ValueError("exact Q released runtime differs")
    if len(routes) != rule["routes"] or any(
        row["cutover_group_revision"] != rule["group"] for row in routes
    ):
        raise ValueError("Q route group revision differs")
    if phase in {"initial", "disabled"}:
        if any(
            row["handler_kind"] != "extension"
            or row["installation_id"] != Q_ID
            or row["generation"] != GENERATION
            or row["execution_epoch"] != 3
            or row["operation_fence"] is not False
            for row in routes
        ):
            raise ValueError("unfenced Q routes required")
    elif phase == "fenced":
        event = next(row for row in routes if row["operation_id"] == "ecommerce_growth_event_control")
        if event["operation_fence"] is not True or any(
            row["operation_fence"] for row in routes if row is not event
        ):
            raise ValueError("only Q event route may be fenced")
    elif phase in {"shrunk", "accepted"}:
        if any(
            row["handler_kind"] != "extension"
            or row["installation_id"] != Q_ID
            or row["generation"] != GENERATION
            or row["execution_epoch"] != 3
            or row["operation_fence"] is not False
            for row in routes
        ):
            raise ValueError("nine unfenced Q routes required")
    else:
        if any(
            row["handler_kind"] != "legacy"
            or row["installation_id"] is not None
            or row["generation"] is not None
            or row["execution_epoch"] is not None
            or row["operation_fence"] is not True
            for row in routes
        ):
            raise ValueError("nine detached Q routes required")
    if phase == "accepted" and (
        operation is None
        or operation["kind"] != "disable"
        or operation["status"] != "accepted"
        or operation["phase"] != "accepted"
        or operation["expected_binding_revision"] != 7
        or lifecycle != {"operations": 0, "receipts": 0, "phases": []}
    ):
        raise ValueError("exact accepted Q disable required")
    if phase == "detached" and (
        operation is None
        or operation["status"] != "succeeded"
        or operation["phase"] != "succeeded"
        or lifecycle != {"operations": 1, "receipts": 2, "phases": ["fence", "detach"]}
    ):
        raise ValueError("exact detached Q lifecycle required")
    return {
        "phase": phase,
        "runtime": dict(runtime),
        "resources": resources,
        "binding": dict(binding),
        "routeCount": len(routes),
        "groupRevision": rule["group"],
        "safety": safety,
        "operation": None if operation is None else dict(operation),
        "lifecycle": lifecycle,
    }


def preflight() -> dict[str, Any]:
    return {
        "outcome": "Q_REBOOT_RETIREMENT_PREFLIGHT_GREEN",
        "state": snapshot("initial"),
        "externalEffects": 0,
    }


def disable_policy12() -> dict[str, Any]:
    load("preflight")
    snapshot("initial")
    from aos_api.ecommerce_growth_runtime_connection import connect_serializable
    from aos_api.ecommerce_released_event_control import (
        ReleasedEventTarget,
        ReleasedProductEventControlService,
    )
    from aos_api.tenant_scope import TenantScope

    policy_result = (
        ROOT.parent
        / ".aos-recovery-20260917/state/q-clean-successor/business/successor-q/product-event-v6/put-result.json"
    )
    if not policy_result.is_file() or policy_result.stat().st_mode & 0o777 != 0o600:
        raise ValueError("exact Q Policy12 authority required")
    policy_ref = json.loads(policy_result.read_text(encoding="utf-8"))["receiptRef"]
    if (
        policy_ref.get("resourceType") != "SchedulePolicyRevision"
        or policy_ref.get("resourceId") != POLICY
        or policy_ref.get("revision") != 12
    ):
        raise ValueError("exact Q Policy12 reference differs")
    command = {
        "schemaVersion": "aos.ecommerce.product-event-control-command/v1",
        "idempotencyKey": PREFIX + "-disable-policy12",
        "policyRef": policy_ref,
        "expectedBindingRevision": 1,
        "intent": "disable",
        "approvalRef": None,
    }
    freeze_or_match(STATE / "disable-policy12-intent.json", command)
    scope = TenantScope(**SCOPE)
    plane = setup()
    receipt = ReleasedProductEventControlService(
        plane.pipeline_control_factory.build_event_control_owner(scope),
        actor=ACTOR,
        connect_factory=connect_serializable,
    ).disable(
        scope=scope,
        command=command,
        target=ReleasedEventTarget(
            installation_id=Q_ID,
            generation=GENERATION,
            execution_epoch=3,
            runtime_revision=7,
            cutover_group_id=GROUP,
            cutover_group_revision=55,
        ),
    )
    return {"outcome": "Q_POLICY12_RELEASED_DISABLE_GREEN", "receipt": receipt, "state": snapshot("disabled")}


def _request(phase: str) -> dict[str, Any]:
    expected = 55 if phase == "fence" else 56
    return {
        "schemaVersion": "aos.ecommerce.event-control-dispatch/v1",
        "phase": phase,
        "installationRef": {
            "installationId": Q_ID,
            "revision": 5,
            "lockHash": LOCK,
            "overlayRevision": "a0v-canonical-ecommerce-v1",
        },
        "generation": GENERATION,
        "executionEpoch": 3,
        "runtimeRevision": 7,
        "cutoverGroupId": GROUP,
        "expectedGroupRevision": expected,
        "caseId": CASE,
        "schedulePolicyId": POLICY,
        "idempotencyKey": PREFIX + "-event-" + phase,
    }


def _approve(payload: dict[str, Any], key: str):
    from psycopg.conninfo import make_conninfo
    from a0v_qyh_current_product_event_first_chain import _approve as approve

    with connect()() as conn:
        parameters = conn.info.get_parameters()
        parameters["password"] = conn.info.password
    prior = os.environ.get("AOS_DATABASE_URL")
    os.environ["AOS_DATABASE_URL"] = make_conninfo(**parameters)
    try:
        return approve("ecommerce_growth_event_dispatch", payload, key)
    finally:
        if prior is None:
            os.environ.pop("AOS_DATABASE_URL", None)
        else:
            os.environ["AOS_DATABASE_URL"] = prior


def _approve_event(phase: str) -> dict[str, Any]:
    predecessor = "disable-policy12" if phase == "fence" else "event-fence"
    load(predecessor)
    snapshot("disabled" if phase == "fence" else "fenced")
    request = _request(phase)
    payload = {"caseId": CASE, "schedulePolicyId": POLICY, "dispatchIntent": request}
    freeze_or_match(STATE / f"approve-event-{phase}-intent.json", payload)
    bundle, ref = _approve(payload, PREFIX + f"-{phase}-approval")
    return {
        "outcome": f"Q_EVENT_{phase.upper()}_APPROVED",
        "request": request,
        "approvalRef": ref,
        "proposalId": bundle.proposal.id,
    }


def approve_event_fence() -> dict[str, Any]:
    return _approve_event("fence")


def approve_event_shrink() -> dict[str, Any]:
    return _approve_event("shrink")


def _event(phase: str) -> dict[str, Any]:
    approved = load("approve-event-" + phase)
    if approved["request"] != _request(phase):
        raise ValueError("Q event transition approval drifted")
    from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
    from aos_api.tenant_scope import TenantScope

    request = EventControlDispatchRequest.model_validate(
        {**approved["request"], "approvalRef": approved["approvalRef"]}
    )
    freeze_or_match(STATE / f"event-{phase}-intent.json", request.wire())
    receipt = setup().pipeline_control_factory.build_event_dispatch_lifecycle(
        TenantScope(**SCOPE)
    ).transition(scope=TenantScope(**SCOPE), request=request, actor=ACTOR)
    target = "fenced" if phase == "fence" else "shrunk"
    return {"outcome": f"Q_RELEASED_EVENT_{phase.upper()}_GREEN", "receipt": receipt, "state": snapshot(target)}


def event_fence() -> dict[str, Any]:
    return _event("fence")


def event_shrink() -> dict[str, Any]:
    return _event("shrink")


def _lifecycle_profile():
    import a0v_ecommerce_current_reinstall as profile

    profile.BUNDLE_ROOT = (
        ROOT.parent
        / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
    )
    return profile


def request_disable() -> dict[str, Any]:
    load("event-shrink")
    snapshot("shrunk")
    profile = _lifecycle_profile()
    current = profile.observe_installation(Q_ID)
    command = profile.require_released_owner_settlement(current)
    intent = {"installationId": Q_ID, **command, "idempotencyKey": PREFIX + "-settle-released"}
    freeze_or_match(STATE / "request-disable-intent.json", intent)
    activation, _store, _lifecycle, service, _dependent = profile._setup_runtime_plane()
    receipt = service.request(
        **SCOPE,
        installation_id=Q_ID,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"],
        if_match='"5"',
        target={"generation": GENERATION, "bindingRevision": command["bindingRevision"]},
    )
    operation_id = receipt.response_json["operationId"]
    return {
        "outcome": "Q_RELEASED_DISABLE_ACCEPTED",
        "operationId": operation_id,
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "state": snapshot("accepted", operation_id),
    }


def process_disable() -> dict[str, Any]:
    requested = load("request-disable")
    operation_id = requested["operationId"]
    snapshot("accepted", operation_id)
    setup()
    profile = _lifecycle_profile()
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    activation, store, _lifecycle, _service, _dependent = profile._setup_runtime_plane()
    consumer = RuntimeDisableConsumer(
        connect=runtime_worker_connection,
        installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(),
        dependent=EcommerceGrowthDisableDependent(),
    )
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(
            conn,
            **SCOPE,
            operation_kind="disable",
            installation_id=Q_ID,
        )
    if lease is None or str(lease.operation_id) != operation_id:
        raise ValueError("exact Q disable delivery required")
    freeze_or_match(
        STATE / "process-disable-intent.json",
        {"operationId": operation_id, "eventId": str(lease.event_id), "resendDisable": False},
    )
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(Q_ID)))
    if (
        str(delivery.operation_id) != operation_id
        or delivery.operation_status != "succeeded"
        or delivery.delivery_status != "acknowledged"
    ):
        raise ValueError("Q disable delivery did not settle")
    return {
        "outcome": "Q_NINE_ROUTES_DETACHED",
        "operationId": operation_id,
        "deliveryStatus": delivery.delivery_status,
        "resendDisable": False,
        "state": snapshot("detached", operation_id),
    }


def audit() -> dict[str, Any]:
    operation_id = load("process-disable")["operationId"]
    return {
        "outcome": "Q_REBOOT_RETIREMENT_GREEN",
        "state": snapshot("detached", operation_id),
        "externalEffects": 0,
    }


def run(action: str) -> dict[str, Any]:
    if action not in ACTIONS:
        raise ValueError("unsupported Q reboot retirement action")
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
