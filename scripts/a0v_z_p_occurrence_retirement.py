#!/usr/bin/env python3
"""Retire P's unaccepted natural-window occurrences through exact negative authorities."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import a0v_p_successor_business as current
from a0v_p_product_window import policy_profile
from a0v_qyh_current_product_event_first_chain import _approve, freeze, freeze_or_match


STATE = current.STATE.parent / "failed-natural-window-retirement-v6"
ABANDONED = current.STATE.parent / "failed-natural-window-v5"
PREFIX = "a0v-qyh-p-policy11-retirement-20260917-v6"
ACTIONS = (
    "preflight", "disable-policy11", "approve-event-fence", "event-fence",
    "prepare-closures", "record-presubmit-recovery", "apply-closures", "audit",
)
PRESUBMIT_OCCURRENCE = "018cec86-17b4-577c-965f-d371afecce78"


def _connect():
    from a0v_formal_text_model_renewal import database_connect
    return database_connect("aos_meta_head")


def _load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def _phase_state(phase: str) -> dict:
    if phase not in {"initial", "disabled", "fenced", "closed"}:
        raise ValueError("fixed P retirement phase required")
    with _connect()() as conn:
        runtime = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,
            desired_state,observed_state FROM extension_runtime_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
              AND generation=%s""", (current.P_ID, current.P_GENERATION)).fetchone()
        resources = [dict(row) for row in conn.execute("""SELECT cleanup_state,observed_release
            FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
              AND generation=%s ORDER BY resource_id""", (current.P_GENERATION,)).fetchall()]
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
            installation_id::text,generation::text,execution_epoch,operation_fence,revision,
            cutover_group_revision FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
            ORDER BY operation_id""", (current.GROUP,)).fetchall()]
        binding = conn.execute("""SELECT policy_revision,revision,enabled,installation_id::text,
            generation::text,execution_epoch FROM automation_schedule_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s
              AND policy_revision=11""", (policy_profile().POLICY,)).fetchone()
        source = conn.execute("""SELECT enabled FROM meta_schedule WHERE org_id='org-org'
            AND project_id='dev-project' AND id='sch-p02-qyh-controlled-20260913-v1'""").fetchone()
        counts = dict(conn.execute("""WITH target AS (
            SELECT o.*,coalesce(a.target_idempotency_key,'automation-occurrence:'||o.occurrence_id::text) target_key,
              a.status attempt_status,a.claim_until,a.receipt_ref attempt_receipt
            FROM automation_occurrence o LEFT JOIN automation_occurrence_dispatch_attempt a
              USING(org_id,project_id,occurrence_id)
            WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.installation_id=%s
              AND o.generation=%s AND o.execution_epoch=3 AND o.trigger_source='event'
              AND o.operation_id='ecommerce_growth_analysis_advance')
          SELECT count(*) total,count(*) FILTER (WHERE status='pending') pending,
            count(*) FILTER (WHERE status='needs_attention') needs_attention,
            count(*) FILTER (WHERE status='cancelled') cancelled,
            count(*) FILTER (WHERE attempt_status='unknown') unknown_attempts,
            count(*) FILTER (WHERE attempt_status='closed_unaccepted') closed_attempts,
            count(*) FILTER (WHERE receipt_ref IS NOT NULL OR attempt_receipt IS NOT NULL) accepted_receipts,
            (SELECT count(*) FROM target t JOIN ecommerce_growth_runtime_command_receipt r
              ON r.org_id=t.org_id AND r.project_id=t.project_id
              AND r.operation_id='ecommerce_growth_analysis_advance' AND r.idempotency_key=t.target_key) target_receipts,
            (SELECT count(*) FROM target t JOIN ecommerce_investigation_run r
              ON r.org_id=t.org_id AND r.project_id=t.project_id
              AND (r.trigger_key=t.target_key OR r.run_id='analysis-'||substr(encode(sha256(convert_to(
                t.org_id||chr(31)||t.project_id||chr(31)||t.target_key,'UTF8')),'hex'),1,32))) target_runs,
            (SELECT count(*) FROM ecommerce_unaccepted_analysis_closure_receipt r
              WHERE r.org_id='org-org' AND r.project_id='dev-project'
                AND r.idempotency_key LIKE %s) closure_receipts,
            (SELECT count(*) FROM extension_operation_dispatch_binding
              WHERE org_id='dev-org' AND project_id='dev-project') canary
          FROM target""", (current.P_ID, current.P_GENERATION, PREFIX + "-close-%")).fetchone())
        abandoned = conn.execute("""SELECT count(*) n FROM ecommerce_product_event_control_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""",
            ("a0v-qyh-p-policy11-failed-window-20260917-v1-disable",)).fetchone()["n"]
    expected_binding = {"initial": (1, True), "disabled": (2, False),
                        "fenced": (2, False), "closed": (2, False)}[phase]
    expected_group = 49 if phase in {"initial", "disabled"} else 50
    if (runtime is None or dict(runtime) != {"revision": 7, "execution_epoch": 4, "enabled": False,
            "operation_fence": True, "desired_state": "enabled", "observed_state": "unknown"}
            or len(resources) != 3 or any(row != {"cleanup_state": "released", "observed_release": True}
                for row in resources) or binding is None
            or (binding["revision"], binding["enabled"]) != expected_binding
            or binding["policy_revision"] != 11 or binding["installation_id"] != current.P_ID
            or binding["generation"] != current.P_GENERATION or binding["execution_epoch"] != 3
            or source is None or source["enabled"] is not False or abandoned != 0
            or len(routes) != 10 or any(row["handler_kind"] != "extension"
                or row["installation_id"] != current.P_ID or row["generation"] != current.P_GENERATION
                or row["execution_epoch"] != 3 or row["cutover_group_revision"] != expected_group
                for row in routes) or counts["total"] != 65 or counts["accepted_receipts"] != 0
            or counts["target_receipts"] != 0 or counts["target_runs"] != 0 or counts["canary"] != 0):
        raise ValueError("exact P released retirement state required")
    event = next(row for row in routes if row["operation_id"] == "ecommerce_growth_event_control")
    if phase in {"initial", "disabled"}:
        if any(row["operation_fence"] for row in routes):
            raise ValueError("unfenced P routes required")
    elif event["operation_fence"] is not True or any(
            row["operation_fence"] for row in routes if row is not event):
        raise ValueError("only the P event route may be fenced")
    expected_occurrences = ((60, 5, 0, 5, 0, 0) if phase != "closed"
                            else (0, 0, 65, 0, 5, 65))
    actual_occurrences = tuple(counts[key] for key in (
        "pending", "needs_attention", "cancelled", "unknown_attempts",
        "closed_attempts", "closure_receipts"))
    if actual_occurrences != expected_occurrences:
        raise ValueError("P occurrence retirement cardinality differs")
    return {"phase": phase, "runtime": dict(runtime), "binding": dict(binding),
            "routeCount": len(routes), "groupRevision": expected_group, "counts": counts,
            "abandonedCommandReceipts": abandoned}


def preflight() -> dict:
    old_intent = ABANDONED / "disable-intent.json"
    old_result = ABANDONED / "disable-result.json"
    if (not old_intent.is_file() or old_intent.stat().st_mode & 0o777 != 0o600
            or old_result.exists()):
        raise ValueError("exact abandoned disable intent without result required")
    return {"outcome": "P_OCCURRENCE_RETIREMENT_PREFLIGHT_GREEN",
            "state": _phase_state("initial"), "externalEffects": 0}


def disable_policy11() -> dict:
    _load("preflight")
    _phase_state("initial")
    policy_ref = policy_profile().load("put")["receiptRef"]
    command = {"schemaVersion": "aos.ecommerce.product-event-control-command/v1",
        "idempotencyKey": PREFIX + "-disable-policy11", "policyRef": policy_ref,
        "expectedBindingRevision": 1, "intent": "disable", "approvalRef": None}
    freeze_or_match(STATE / "disable-policy11-intent.json", command)
    from aos_api.ecommerce_growth_runtime_connection import connect_serializable
    from aos_api.ecommerce_released_event_control import ReleasedEventTarget, ReleasedProductEventControlService
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope("org-org", "dev-project")
    plane = current.setup()
    receipt = ReleasedProductEventControlService(
        plane.pipeline_control_factory.build_event_control_owner(scope), actor=current.ACTOR,
        connect_factory=connect_serializable).disable(scope=scope, command=command,
        target=ReleasedEventTarget(installation_id=current.P_ID, generation=current.P_GENERATION,
            execution_epoch=3, runtime_revision=7, cutover_group_id=current.GROUP,
            cutover_group_revision=49))
    return {"outcome": "P_POLICY11_RELEASED_DISABLE_GREEN", "receipt": receipt,
            "state": _phase_state("disabled")}


def _fence_request() -> dict:
    return {"schemaVersion": "aos.ecommerce.event-control-dispatch/v1", "phase": "fence",
        "installationRef": {"installationId": current.P_ID, "revision": 5,
            "lockHash": current.LOCK, "overlayRevision": "a0v-canonical-ecommerce-v1"},
        "generation": current.P_GENERATION, "executionEpoch": 3, "runtimeRevision": 7,
        "cutoverGroupId": current.GROUP, "expectedGroupRevision": 49,
        "caseId": policy_profile().CASE, "schedulePolicyId": policy_profile().POLICY,
        "idempotencyKey": PREFIX + "-event-fence"}


def approve_event_fence() -> dict:
    _load("disable-policy11")
    _phase_state("disabled")
    request = _fence_request()
    payload = {"caseId": policy_profile().CASE, "schedulePolicyId": policy_profile().POLICY,
               "dispatchIntent": request}
    freeze_or_match(STATE / "approve-event-fence-intent.json", payload)
    from psycopg.conninfo import make_conninfo
    with _connect()() as conn:
        parameters = conn.info.get_parameters()
        parameters["password"] = conn.info.password
    previous = os.environ.get("AOS_DATABASE_URL")
    os.environ["AOS_DATABASE_URL"] = make_conninfo(**parameters)
    try:
        bundle, ref = _approve("ecommerce_growth_event_dispatch", payload, PREFIX + "-fence-approval")
    finally:
        if previous is None:
            os.environ.pop("AOS_DATABASE_URL", None)
        else:
            os.environ["AOS_DATABASE_URL"] = previous
    return {"outcome": "P_EVENT_FENCE_APPROVED", "request": request,
            "approvalRef": ref, "proposalId": bundle.proposal.id}


def event_fence() -> dict:
    approved = _load("approve-event-fence")
    if approved["request"] != _fence_request():
        raise ValueError("P event fence approval drifted")
    from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
    from aos_api.tenant_scope import TenantScope
    request = EventControlDispatchRequest.model_validate(
        {**approved["request"], "approvalRef": approved["approvalRef"]})
    freeze_or_match(STATE / "event-fence-intent.json", request.wire())
    scope = TenantScope("org-org", "dev-project")
    receipt = current.setup().pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(
        scope=scope, request=request, actor=current.ACTOR)
    return {"outcome": "P_RELEASED_EVENT_FENCE_GREEN", "receipt": receipt,
            "state": _phase_state("fenced")}


def prepare_closures() -> dict:
    fence = _load("event-fence")["receipt"]
    _phase_state("fenced")
    with _connect()() as conn:
        rows = conn.execute("""SELECT o.occurrence_id,o.status,
          coalesce(a.target_idempotency_key,'automation-occurrence:'||o.occurrence_id::text) target_key
          FROM automation_occurrence o LEFT JOIN automation_occurrence_dispatch_attempt a
            USING(org_id,project_id,occurrence_id)
          WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.installation_id=%s
            AND o.generation=%s AND o.execution_epoch=3 AND o.trigger_source='event'
            AND o.operation_id='ecommerce_growth_analysis_advance'
            AND ((o.status='needs_attention' AND a.status='unknown' AND a.claim_until<clock_timestamp()
              AND a.receipt_ref IS NULL) OR (o.status='pending' AND a.attempt_id IS NULL))
          ORDER BY o.occurrence_id""", (current.P_ID, current.P_GENERATION)).fetchall()
    if len(rows) != 65 or sum(row["status"] == "needs_attention" for row in rows) != 5:
        raise ValueError("exact P 5 unknown plus 60 pending occurrences required")
    requests = [{"schemaVersion": "aos.ecommerce.unaccepted-analysis-closure/v1",
        "occurrenceId": str(row["occurrence_id"]), "fenceReceiptId": fence["receiptId"],
        "fenceContentHash": fence["contentHash"],
        "idempotencyKey": PREFIX + "-close-" + str(row["occurrence_id"])} for row in rows]
    plan = {"installationId": current.P_ID, "generation": current.P_GENERATION,
        "actor": current.ACTOR, "count": 65, "unknownCount": 5, "pendingCount": 60,
        "businessAccepted": False, "externalEffects": False, "requests": requests}
    freeze_or_match(STATE / "closure-plan.json", plan)
    return {"outcome": "P_65_UNACCEPTED_CLOSURES_PLANNED", "count": 65,
            "unknownCount": 5, "pendingCount": 60}


def _read_existing(request: dict) -> dict | None:
    from aos_api.asset_registry.canonical_json import canonical_sha256
    with _connect()() as conn:
        row = conn.execute("""SELECT authority_data,content_hash,request_hash,actor
          FROM ecommerce_unaccepted_analysis_closure_receipt WHERE org_id='org-org'
            AND project_id='dev-project' AND idempotency_key=%s""",
            (request["idempotencyKey"],)).fetchone()
    if row is None:
        return None
    if (row["actor"] != current.ACTOR or row["request_hash"] != canonical_sha256(request)
            or row["content_hash"] != canonical_sha256(row["authority_data"])):
        raise ValueError("prior P closure intent needs inspection; do not resend")
    return {**row["authority_data"], "contentHash": row["content_hash"], "replayed": True}


def record_presubmit_recovery() -> dict:
    _load("prepare-closures")
    plan = json.loads((STATE / "closure-plan.json").read_text(encoding="utf-8"))
    request = next((row for row in plan.get("requests", [])
                    if row.get("occurrenceId") == PRESUBMIT_OCCURRENCE), None)
    intent = STATE / "closures" / f"{PRESUBMIT_OCCURRENCE}-intent.json"
    result = STATE / "closures" / f"{PRESUBMIT_OCCURRENCE}-result.json"
    intents = sorted((STATE / "closures").glob("*-intent.json"))
    results = sorted((STATE / "closures").glob("*-result.json"))
    if (request is None or len(intents) != 1 or intents[0] != intent or results or result.exists()
            or json.loads(intent.read_text(encoding="utf-8")) != request
            or _read_existing(request) is not None):
        raise ValueError("exact known pre-connection closure failure required")
    proof = {"schemaVersion": "aos.recovery.known-presubmit/v1",
        "occurrenceId": PRESUBMIT_OCCURRENCE, "idempotencyKey": request["idempotencyKey"],
        "failureStage": "registration_identity_validation_before_connection",
        "receiptCount": 0, "resultFilePresent": False}
    freeze_or_match(STATE / "closure-presubmit-recovery.json", proof)
    return {"outcome": "P_FIRST_CLOSURE_KNOWN_PRESUBMIT_RECOVERY_RECORDED",
            "occurrenceId": PRESUBMIT_OCCURRENCE, "receiptCount": 0}


def apply_closures() -> dict:
    _load("prepare-closures")
    _load("record-presubmit-recovery")
    current.setup()
    plan = json.loads((STATE / "closure-plan.json").read_text(encoding="utf-8"))
    if (plan.get("installationId") != current.P_ID or plan.get("generation") != current.P_GENERATION
            or plan.get("actor") != current.ACTOR or plan.get("count") != 65
            or len(plan.get("requests", [])) != 65
            or len({row["occurrenceId"] for row in plan["requests"]}) != 65):
        raise ValueError("exact immutable P closure plan required")
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.ecommerce_unaccepted_analysis_closure import (
        UnacceptedAnalysisClosureRequest, UnacceptedAnalysisClosureService,
    )
    from aos_api.tenant_scope import TenantScope
    service = UnacceptedAnalysisClosureService(connect=registration_connection)
    scope = TenantScope("org-org", "dev-project")
    receipts = []
    for wire in plan["requests"]:
        request = UnacceptedAnalysisClosureRequest.model_validate(wire)
        intent = STATE / "closures" / f"{request.occurrence_id}-intent.json"
        if intent.exists():
            if json.loads(intent.read_text(encoding="utf-8")) != wire:
                raise ValueError("retained P closure intent drifted")
            receipt = _read_existing(wire)
            if receipt is None:
                proof = json.loads((STATE / "closure-presubmit-recovery.json").read_text(encoding="utf-8"))
                expected = {"schemaVersion": "aos.recovery.known-presubmit/v1",
                    "occurrenceId": request.occurrence_id, "idempotencyKey": request.idempotency_key,
                    "failureStage": "registration_identity_validation_before_connection",
                    "receiptCount": 0, "resultFilePresent": False}
                if proof != expected or request.occurrence_id != PRESUBMIT_OCCURRENCE:
                    raise ValueError("intent without Receipt requires exact presubmit proof")
                receipt = service.close(scope=scope, request=request, actor=current.ACTOR)
        else:
            freeze(intent, wire)
            receipt = service.close(scope=scope, request=request, actor=current.ACTOR)
        result = STATE / "closures" / f"{request.occurrence_id}-result.json"
        if not result.exists():
            freeze(result, receipt)
        receipts.append({"receiptId": receipt["receiptId"], "contentHash": receipt["contentHash"]})
    return {"outcome": "P_65_UNACCEPTED_OCCURRENCES_CLOSED", "count": len(receipts),
            "businessAccepted": False, "state": _phase_state("closed")}


def audit() -> dict:
    _load("apply-closures")
    return {"outcome": "P_OCCURRENCE_RETIREMENT_GREEN", "state": _phase_state("closed"),
            "businessAccepted": False, "externalEffects": 0}


def run(action: str) -> dict:
    if action not in ACTIONS:
        raise ValueError("unsupported P occurrence retirement action")
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
