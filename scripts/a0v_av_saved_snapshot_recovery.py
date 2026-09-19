#!/usr/bin/env python3
"""Transfer the one frozen snapshot group from AU to AV without rereading its source."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os

import a0v_u_twelve_source_snapshot as snapshot
import a0v_av_replacement_recovery as replacement
import a0v_av_successor_business as successor
import a0v_at_successor_business as snapshot_predecessor
from a0v_qyh_current_product_event_first_chain import freeze


STATE = snapshot.STATE.parent / "av-saved-snapshot-recovery-v1"
GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
MANIFEST = "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01"
ACTIONS = ("prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "pause-terminal", "disable")
INSTALLATION_LABEL = "AV"
PREDECESSOR_INSTALLATION_ID = snapshot_predecessor.AT_ID
PREDECESSOR_DEFINITION_REVISION = 73
TRANSFERRED_DEFINITION_REVISION = 74
RECOVERY_REVISION = 24
ENABLED_DEFINITION_REVISION = 75
PAUSED_DEFINITION_REVISION = 76
PREDECESSOR_RECOVERY_STATE = "at-saved-snapshot-recovery-v1"
CONTROL_PREFIX = "a0v-av-snapshot"
DISABLE_KEY = "a0v-av-saved-snapshot-disable-complete-v1"
TRANSFER_KEY = "a0v-av-saved-definition-transfer-v1"
RENEW_KEY = "a0v-av-saved-input-recovery-v24"
PAUSE_KEY = "a0v-av-saved-snapshot-pause-terminal-v1"
TERMINAL_FREEZE_OUTCOMES = {"ABANDONED_WAIT_NATURAL_SUCCESSOR"}
EXPECTED_TERMINAL_ATTEMPT_COUNT = 1


def attempt_guard_module():
    import a0v_av_attempt_guard as guard
    return guard

def profile():
    snapshot.STATE = STATE
    snapshot.current.U_ID = replacement.load("create-av")["installationId"]
    snapshot.current.U_GENERATION = successor.AV_GENERATION
    snapshot.CONTROL_PREFIX = CONTROL_PREFIX
    snapshot.DISABLE_KEY = DISABLE_KEY
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
        raise RuntimeError(f"exact {INSTALLATION_LABEL} preview required")
    return {**value, "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_PREPARED"}


def schedule_ingest(plane):
    profile()
    value = snapshot.schedule_ingest(plane)
    return {**value, "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_SCHEDULES_CONFIRMED"}


def controls(plane):
    profile()
    value = snapshot.controls(plane)
    return {**value, "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_CONTROLS_CURRENT"}


def service_and_options(plane):
    from aos_api.tenant_scope import TenantScope

    installation, generation = profile()
    service = plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE), source_controls=True
    )
    options = service.options(actor=snapshot.ACTOR, installation_id=installation, generation=generation)
    if options.get("status") != "ready" or len(options.get("members", [])) != 12 or not options.get("policies"):
        raise RuntimeError(f"exact {INSTALLATION_LABEL} twelve-source options required")
    confirmed = {item["scheduleId"]: item for item in load("controls")["members"]}
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]} for item in options["members"]]
    if any(confirmed.get(item["scheduleId"], {}).get("bindingRef") != item["bindingRef"] for item in members):
        raise RuntimeError("AU options differ from frozen controls")
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
        or current["body"]["installationId"] != PREDECESSOR_INSTALLATION_ID
        or current["body"]["revision"] != PREDECESSOR_DEFINITION_REVISION
    ):
        raise RuntimeError("exact disabled predecessor definition required")
    original = json.loads(
        (snapshot.STATE.parent / PREDECESSOR_RECOVERY_STATE / "renew-result.json").read_text(encoding="utf-8")
    )
    recovery_ref = original["recovery"]["receipt"]["ref"]
    result = service.transfer_saved_recovery(
        definition_id=snapshot.DEFINITION_ID,
        group_id=GROUP,
        actor=snapshot.ACTOR,
        members=members,
        expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref,
        idempotency_key=TRANSFER_KEY,
    )
    if (
        result.get("ref", {}).get("revision") != TRANSFERRED_DEFINITION_REVISION
        or result.get("body", {}).get("revision") != TRANSFERRED_DEFINITION_REVISION
        or result.get("body", {}).get("priorRef") != current["ref"]
        or result.get("body", {}).get("installationId") != successor.AV_ID
        or result.get("body", {}).get("generation") != successor.AV_GENERATION
        or result.get("body", {}).get("state") != "disabled"
    ):
        raise RuntimeError(f"exact disabled {INSTALLATION_LABEL} transferred definition required")
    return {
        "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED",
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
        raise RuntimeError(f"exact {INSTALLATION_LABEL} transferred saved recovery context required")
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
        idempotency_key=RENEW_KEY,
    )
    receipt = result.get("receipt", {})
    if (
        result.get("executionStarted") is not False
        or receipt.get("ref", {}).get("revision") != RECOVERY_REVISION
        or receipt.get("body", {}).get("revision") != RECOVERY_REVISION
        or receipt.get("body", {}).get("priorRef") != context["expectedRecoveryRef"]
        or receipt.get("body", {}).get("currentDefinitionRef", {}).get("revision") != ENABLED_DEFINITION_REVISION
        or receipt.get("body", {}).get("inputManifestHash") != MANIFEST
    ):
        raise RuntimeError(f"exact {INSTALLATION_LABEL} renewed recovery authority required")
    return {
        "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_RECOVERY_RENEWED",
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
        raise RuntimeError(f"current enabled {INSTALLATION_LABEL} saved recovery authority required")
    return {
        "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_RECOVERY_ENABLED_CONFIRMED",
        "definition": status,
        "recoveryRef": renewed["ref"],
        "sourceReads": 0,
    }



def inspect(plane):
    profile()
    return snapshot.inspect(plane) | {
        "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_INSPECTED", "sourceReads": 0}


def pause_terminal(plane):
    """Disable only the exact abandoned AV boundary before formal retirement."""
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

    guard = attempt_guard_module()
    profile()
    service = snapshot_service(plane)
    status = service.read_runtime_status(definition_id=snapshot.DEFINITION_ID, actor=snapshot.ACTOR)
    if (status.get("configurationState") != "enabled"
            or status["definitionRef"]["revision"] != ENABLED_DEFINITION_REVISION):
        raise RuntimeError(f"exact enabled {INSTALLATION_LABEL} terminal recovery definition required")
    with consumer_connection(runtime_worker_connection, snapshot.baseline.SCOPE) as conn:
        facts = guard.read_facts(conn)
    classified = guard.classify(facts)
    expected = {
        "attemptCount": EXPECTED_TERMINAL_ATTEMPT_COUNT,
        "runningRuns": 12, "succeededRuns": 0, "failedRuns": 0,
        "retirements": 0, "linkStoreReceipts": 0, "ecomLinks": 0,
        "linkOutbox": 0, "projectionPending": 0,
    }
    observed = {key: facts[key] for key in expected}
    if classified["outcome"] not in TERMINAL_FREEZE_OUTCOMES or observed != expected:
        raise RuntimeError(f"exact terminal {INSTALLATION_LABEL} saved recovery facts required: {observed}")
    result = service.transition(
        definition_id=snapshot.DEFINITION_ID,
        actor=snapshot.ACTOR,
        intent="disable",
        expected_ref=status["definitionRef"],
        idempotency_key=PAUSE_KEY,
    )
    if (result.get("ref", {}).get("revision") != PAUSED_DEFINITION_REVISION
            or result.get("body", {}).get("state") != "disabled"):
        raise RuntimeError(f"exact disabled {INSTALLATION_LABEL} terminal definition required")
    return {
        "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_TERMINAL_RECOVERY_PAUSED",
        "attemptId": guard.ATTEMPT_ID,
        "facts": {"outcome": classified["outcome"]} | expected,
        "definition": result, "sourceReads": 0,
    }


def disable(plane):
    profile()
    value = snapshot.disable(plane)
    return {**value, "outcome": f"{INSTALLATION_LABEL}_SAVED_SNAPSHOT_COMPLETE_DISABLED", "sourceReads": 0}


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
