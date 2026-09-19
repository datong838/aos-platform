#!/usr/bin/env python3
"""Transfer the one frozen snapshot group from AR to AS without rereading its source."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os

import a0v_u_twelve_source_snapshot as snapshot
import a0v_as_replacement_recovery as replacement
import a0v_as_successor_business as successor
from a0v_qyh_current_product_event_first_chain import freeze


STATE = snapshot.STATE.parent / "as-saved-snapshot-recovery-v1"
GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
MANIFEST = "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01"
ACTIONS = ("prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "pause-failed", "disable")
ATTEMPT_ID = "af7c1fc1-8283-40d7-ab62-f7d6145417c6"

def profile():
    snapshot.STATE = STATE
    snapshot.current.U_ID = replacement.load("create-as")["installationId"]
    snapshot.current.U_GENERATION = successor.AS_GENERATION
    snapshot.CONTROL_PREFIX = "a0v-as-snapshot"
    snapshot.DISABLE_KEY = "a0v-as-saved-snapshot-disable-complete-v1"
    snapshot.preview.INSTALLATION = snapshot.current.U_ID
    snapshot.preview.GENERATION = snapshot.current.U_GENERATION
    return snapshot.current.U_ID, snapshot.current.U_GENERATION


def load(name):
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(plane):
    installation, generation = profile()
    value = snapshot.prepare(plane)
    if (value["installationRef"]["installationId"], value["generation"]) != (installation, generation):
        raise RuntimeError("exact AS preview required")
    return {**value, "outcome": "AS_SAVED_SNAPSHOT_PREPARED"}


def schedule_ingest(plane):
    profile()
    value = snapshot.schedule_ingest(plane)
    return {**value, "outcome": "AS_SAVED_SNAPSHOT_SCHEDULES_CONFIRMED"}


def controls(plane):
    profile()
    value = snapshot.controls(plane)
    return {**value, "outcome": "AS_SAVED_SNAPSHOT_CONTROLS_CURRENT"}


def service_and_options(plane):
    from aos_api.tenant_scope import TenantScope

    installation, generation = profile()
    service = plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE), source_controls=True
    )
    options = service.options(actor=snapshot.ACTOR, installation_id=installation, generation=generation)
    if options.get("status") != "ready" or len(options.get("members", [])) != 12 or not options.get("policies"):
        raise RuntimeError("exact AS twelve-source options required")
    confirmed = {item["scheduleId"]: item for item in load("controls")["members"]}
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]} for item in options["members"]]
    if any(confirmed.get(item["scheduleId"], {}).get("bindingRef") != item["bindingRef"] for item in members):
        raise RuntimeError("AS options differ from frozen controls")
    return service, members


def snapshot_service(plane):
    from aos_api.tenant_scope import TenantScope

    profile()
    return plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE), source_controls=True
    )


def transfer(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    service, members = service_and_options(plane)
    scope = TenantScope(**snapshot.baseline.SCOPE)
    with consumer_connection(runtime_worker_connection, snapshot.baseline.SCOPE) as conn:
        current = service._owner.read(conn, scope=scope, definition_id=snapshot.DEFINITION_ID)
    if (
        current is None
        or current["body"]["state"] != "disabled"
        or current["body"]["installationId"] != successor.AR_ID
        or current["body"]["revision"] != 67
    ):
        raise RuntimeError("exact disabled AR definition revision67 required")
    original = json.loads(
        (snapshot.STATE.parent / "aq-saved-snapshot-recovery-v1" / "renew-result.json").read_text(encoding="utf-8")
    )
    recovery_ref = original["recovery"]["receipt"]["ref"]
    result = service.transfer_saved_recovery(
        definition_id=snapshot.DEFINITION_ID,
        group_id=GROUP,
        actor=snapshot.ACTOR,
        members=members,
        expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref,
        idempotency_key="a0v-as-saved-definition-transfer-v1",
    )
    if (
        result.get("ref", {}).get("revision") != 68
        or result.get("body", {}).get("revision") != 68
        or result.get("body", {}).get("priorRef") != current["ref"]
        or result.get("body", {}).get("installationId") != successor.AS_ID
        or result.get("body", {}).get("generation") != successor.AS_GENERATION
        or result.get("body", {}).get("state") != "disabled"
    ):
        raise RuntimeError("exact disabled AS definition revision68 required")
    return {
        "outcome": "AS_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED",
        "definition": result,
        "groupId": GROUP,
        "inputManifestHash": MANIFEST,
        "sourceReads": 0,
    }


def renew(plane):
    service, _ = service_and_options(plane)
    transferred = load("transfer")["definition"]
    context = service.read_recovery_context(group_id=GROUP, actor=snapshot.ACTOR)
    if (
        context["expectedDefinitionRef"] != transferred["ref"]
        or context["inputManifestHash"] != MANIFEST
        or context["expectedRecoveryRef"] is None
    ):
        raise RuntimeError("exact AS transferred saved recovery context required")
    now = datetime.fromisoformat(context["windowRules"]["currentTime"])
    expires = now + timedelta(hours=6)
    if expires <= datetime.fromisoformat(context["windowRules"]["expiresAfter"]):
        raise RuntimeError("six-hour saved recovery window does not advance predecessor")
    result = service.renew_saved_group(
        group_id=GROUP,
        actor=snapshot.ACTOR,
        expected_definition_ref=context["expectedDefinitionRef"],
        expected_recovery_ref=context["expectedRecoveryRef"],
        input_manifest_hash=MANIFEST,
        not_before=now,
        expires_at=expires,
        idempotency_key="a0v-as-saved-input-recovery-v22",
    )
    receipt = result.get("receipt", {})
    if (
        result.get("executionStarted") is not False
        or receipt.get("ref", {}).get("revision") != 22
        or receipt.get("body", {}).get("revision") != 22
        or receipt.get("body", {}).get("priorRef") != context["expectedRecoveryRef"]
        or receipt.get("body", {}).get("currentDefinitionRef", {}).get("revision") != 69
        or receipt.get("body", {}).get("inputManifestHash") != MANIFEST
    ):
        raise RuntimeError("exact AS recovery revision22 and enabled definition revision69 required")
    return {
        "outcome": "AS_SAVED_SNAPSHOT_RECOVERY_RENEWED",
        "context": context,
        "recovery": result,
        "sourceReads": 0,
    }


def enable(plane):
    service = snapshot_service(plane)
    renewed = load("renew")["recovery"]["receipt"]
    status = service.read_runtime_status(definition_id=snapshot.DEFINITION_ID, actor=snapshot.ACTOR)
    context = service.read_recovery_context(group_id=GROUP, actor=snapshot.ACTOR)
    if (
        status.get("configurationState") != "enabled"
        or status.get("definitionRef") != renewed["body"]["currentDefinitionRef"]
        or context.get("expectedDefinitionRef") != renewed["body"]["currentDefinitionRef"]
        or context.get("expectedRecoveryRef") != renewed["ref"]
    ):
        raise RuntimeError("current enabled AS saved recovery authority required")
    return {
        "outcome": "AS_SAVED_SNAPSHOT_RECOVERY_ENABLED_CONFIRMED",
        "definition": status,
        "recoveryRef": renewed["ref"],
        "sourceReads": 0,
    }



def inspect(plane):
    profile()
    return snapshot.inspect(plane) | {"outcome": "AS_SAVED_SNAPSHOT_INSPECTED", "sourceReads": 0}


def pause_failed(plane):
    """Disable only the exact failed AS boundary before successor work."""
    import a0v_as_attempt_guard as guard
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

    profile()
    service = snapshot_service(plane)
    status = service.read_runtime_status(definition_id=snapshot.DEFINITION_ID, actor=snapshot.ACTOR)
    if status.get("configurationState") != "enabled" or status["definitionRef"]["revision"] != 69:
        raise RuntimeError("exact enabled AS failed recovery definition revision69 required")
    with consumer_connection(runtime_worker_connection, snapshot.baseline.SCOPE) as conn:
        facts = guard.read_facts(conn)
    classified = guard.classify(facts)
    expected = {
        "outcome": "FAILED_FREEZE_BOUNDARY",
        "runningRuns": 12,
        "succeededRuns": 0,
        "failedRuns": 0,
        "retirements": 0,
        "linkStoreReceipts": 0,
        "ecomLinks": 0,
        "linkOutbox": 0,
        "projectionPending": 0,
    }
    observed = {"outcome": classified["outcome"]} | {
        key: facts[key] for key in expected if key != "outcome"
    }
    if observed != expected:
        raise RuntimeError(f"exact failed AS saved recovery facts required: {observed}")
    result = service.transition(
        definition_id=snapshot.DEFINITION_ID,
        actor=snapshot.ACTOR,
        intent="disable",
        expected_ref=status["definitionRef"],
        idempotency_key="a0v-as-saved-snapshot-pause-failed-v1",
    )
    if result.get("ref", {}).get("revision") != 70 or result.get("body", {}).get("state") != "disabled":
        raise RuntimeError("exact disabled AS definition revision70 required")
    return {
        "outcome": "AS_SAVED_SNAPSHOT_FAILED_RECOVERY_PAUSED",
        "attemptId": ATTEMPT_ID,
        "facts": expected,
        "definition": result,
        "sourceReads": 0,
    }


def disable(plane):
    profile()
    value = snapshot.disable(plane)
    return {**value, "outcome": "AS_SAVED_SNAPSHOT_COMPLETE_DISABLED", "sourceReads": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    profile()
    _previous, _preflight, plane = snapshot.baseline.setup()
    value = globals()[args.action.replace("-", "_")](plane)
    if args.action != "inspect":
        output = STATE / f"{args.action}-result.json"
        if output.exists():
            raise RuntimeError(f"immutable {args.action} output exists")
        freeze(output, value)
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
