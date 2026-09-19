#!/usr/bin/env python3
"""Transfer the one frozen snapshot group from AN to AO without rereading its source."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os

import a0v_u_twelve_source_snapshot as snapshot
import a0v_ao_replacement_recovery as replacement
import a0v_ao_successor_business as successor
from a0v_qyh_current_product_event_first_chain import freeze


STATE = snapshot.STATE.parent / "ao-saved-snapshot-recovery-v1"
GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
MANIFEST = "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01"
ACTIONS = ("prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "disable")
ATTEMPT_ID = "67c2331d-b73f-4863-b881-0d67e6c55508"
LINK_COMMAND_HASH = "sha256:f16b566f1974831e0c662ea67049c77acc1febd12c7bd8ff98e9651d0d396970"
LINK_IDEMPOTENCY_KEY = (
    "snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:"
    "bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b"
)


def profile():
    snapshot.STATE = STATE
    snapshot.current.U_ID = replacement.load("create-ao")["installationId"]
    snapshot.current.U_GENERATION = successor.AO_GENERATION
    snapshot.CONTROL_PREFIX = "a0v-ao-snapshot"
    snapshot.DISABLE_KEY = "a0v-ao-saved-snapshot-disable-complete-v1"
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
        raise RuntimeError("exact AO preview required")
    return {**value, "outcome": "AO_SAVED_SNAPSHOT_PREPARED"}


def schedule_ingest(plane):
    profile()
    value = snapshot.schedule_ingest(plane)
    return {**value, "outcome": "AO_SAVED_SNAPSHOT_SCHEDULES_CONFIRMED"}


def controls(plane):
    profile()
    value = snapshot.controls(plane)
    return {**value, "outcome": "AO_SAVED_SNAPSHOT_CONTROLS_CURRENT"}


def service_and_options(plane):
    from aos_api.tenant_scope import TenantScope

    installation, generation = profile()
    service = plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**snapshot.baseline.SCOPE), source_controls=True
    )
    options = service.options(actor=snapshot.ACTOR, installation_id=installation, generation=generation)
    if options.get("status") != "ready" or len(options.get("members", [])) != 12 or not options.get("policies"):
        raise RuntimeError("exact AO twelve-source options required")
    confirmed = {item["scheduleId"]: item for item in load("controls")["members"]}
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]} for item in options["members"]]
    if any(confirmed.get(item["scheduleId"], {}).get("bindingRef") != item["bindingRef"] for item in members):
        raise RuntimeError("AO options differ from frozen controls")
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
        or current["body"]["installationId"] != successor.AN_ID
        or current["body"]["revision"] != 57
    ):
        raise RuntimeError("exact disabled AN definition revision57 required")
    original = json.loads(
        (snapshot.STATE.parent / "an-saved-snapshot-recovery-v1" / "renew-result.json").read_text(encoding="utf-8")
    )
    recovery_ref = original["recovery"]["receipt"]["ref"]
    result = service.transfer_saved_recovery(
        definition_id=snapshot.DEFINITION_ID,
        group_id=GROUP,
        actor=snapshot.ACTOR,
        members=members,
        expected_ref=current["ref"],
        expected_recovery_ref=recovery_ref,
        idempotency_key="a0v-ao-saved-definition-transfer-v1",
    )
    if (
        result.get("ref", {}).get("revision") != 58
        or result.get("body", {}).get("revision") != 58
        or result.get("body", {}).get("priorRef") != current["ref"]
        or result.get("body", {}).get("installationId") != successor.AO_ID
        or result.get("body", {}).get("generation") != successor.AO_GENERATION
        or result.get("body", {}).get("state") != "disabled"
    ):
        raise RuntimeError("exact disabled AO definition revision58 required")
    return {
        "outcome": "AO_SAVED_SNAPSHOT_DEFINITION_TRANSFERRED",
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
        raise RuntimeError("exact AO transferred saved recovery context required")
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
        idempotency_key="a0v-ao-saved-input-recovery-v19",
    )
    receipt = result.get("receipt", {})
    if (
        result.get("executionStarted") is not False
        or receipt.get("ref", {}).get("revision") != 19
        or receipt.get("body", {}).get("revision") != 19
        or receipt.get("body", {}).get("priorRef") != context["expectedRecoveryRef"]
        or receipt.get("body", {}).get("currentDefinitionRef", {}).get("revision") != 59
        or receipt.get("body", {}).get("inputManifestHash") != MANIFEST
    ):
        raise RuntimeError("exact AO recovery revision19 and enabled definition revision59 required")
    return {
        "outcome": "AO_SAVED_SNAPSHOT_RECOVERY_RENEWED",
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
        raise RuntimeError("current enabled AO saved recovery authority required")
    return {
        "outcome": "AO_SAVED_SNAPSHOT_RECOVERY_ENABLED_CONFIRMED",
        "definition": status,
        "recoveryRef": renewed["ref"],
        "sourceReads": 0,
    }


def terminal_facts():
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

    installation, generation = profile()
    scope = snapshot.baseline.SCOPE
    query = """SELECT
      (SELECT count(*) FROM extension_runtime_execution_attempt
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
          AND operation_kind='recoverable_store' AND operation_key=%s AND state='succeeded'
          AND completed_at IS NOT NULL AND terminal_reason_code IS NULL) succeeded_attempt,
      (SELECT count(*) FROM extension_runtime_execution_attempt
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
          AND attempt_id=%s AND operation_kind='recoverable_store' AND state='abandoned'
          AND terminal_reason_code='ATTEMPT_LEASE_EXPIRED'
          AND terminal_error_type IS NULL) abandoned_attempts,
      (SELECT count(*) FROM extension_runtime_execution_attempt
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
          AND operation_kind='recoverable_store') attempts,
      (SELECT count(*) FROM pipeline_snapshot_schedule_member
        WHERE org_id=%s AND project_id=%s AND group_id=%s) members,
      (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
        ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
        WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
          AND r.status='succeeded' AND r.executor_stopped IS TRUE
          AND r.finished_at IS NOT NULL) succeeded_runs,
      (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d
        JOIN pipeline_snapshot_schedule_member m
          ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
        WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s) dataset_receipts,
      (SELECT count(*) FROM pipeline_snapshot_group_relationship
        WHERE org_id=%s AND project_id=%s AND group_id=%s) relationships,
      (SELECT count(*) FROM pipeline_snapshot_group_link_command
        WHERE org_id=%s AND project_id=%s AND group_id=%s AND command_hash=%s) link_commands,
      (SELECT coalesce(max(link_count),0) FROM pipeline_snapshot_group_link_command
        WHERE org_id=%s AND project_id=%s AND group_id=%s AND command_hash=%s) link_count,
      (SELECT count(*) FROM pipeline_snapshot_group_retirement
        WHERE org_id=%s AND project_id=%s AND group_id=%s) retirements,
      (SELECT count(*) FROM ecom_ingest_receipt
        WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s) store_receipts,
      (SELECT count(*) FROM ecom_link
        WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL) live_links,
      (SELECT count(*) FROM projection_outbox
        WHERE org_id=%s AND workspace_id=%s AND event_source='authoritative_store'
          AND change_kind=ANY(ARRAY['links_written','links_tombstoned'])) store_outbox,
      (SELECT count(*) FROM projection_outbox
        WHERE org_id=%s AND workspace_id=%s AND projected IS FALSE) projection_pending,
      (SELECT count(*) FROM extension_operation_dispatch_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
          AND execution_epoch=3 AND operation_fence IS FALSE
          AND revision=96 AND cutover_group_revision=123) routes,
      (SELECT count(*) FROM extension_runtime_resource_lease
        WHERE org_id=%s AND project_id=%s AND generation=%s
          AND cleanup_state='pending' AND observed_release IS FALSE) live_resources,
      (SELECT count(*) FROM extension_runtime_binding
        WHERE org_id='dev-org' AND project_id='dev-project') canary"""
    parameters = (
        *scope.values(), installation, generation,
        "snapshot-group-completion:" + GROUP,
        *scope.values(), installation, generation, ATTEMPT_ID,
        *scope.values(), installation, generation,
        *scope.values(), GROUP,
        *scope.values(), GROUP,
        *scope.values(), GROUP,
        *scope.values(), GROUP,
        *scope.values(), GROUP, LINK_COMMAND_HASH,
        *scope.values(), GROUP, LINK_COMMAND_HASH,
        *scope.values(), GROUP,
        scope["org_id"], scope["project_id"], LINK_IDEMPOTENCY_KEY,
        scope["org_id"], scope["project_id"],
        scope["org_id"], scope["project_id"],
        scope["org_id"], scope["project_id"],
        *scope.values(), installation, generation,
        *scope.values(), generation,
    )
    if query.count("%s") != len(parameters):
        raise RuntimeError("AO terminal fact query binding differs")
    with consumer_connection(runtime_worker_connection, scope) as conn:
        return dict(conn.execute(query, parameters).fetchone())


def require_terminal_facts() -> dict:
    facts = terminal_facts()
    expected = {
        "succeeded_attempt": 1,
        "abandoned_attempts": 1,
        "attempts": 2,
        "members": 12,
        "succeeded_runs": 12,
        "dataset_receipts": 12,
        "relationships": 1,
        "link_commands": 1,
        "link_count": 1168,
        "retirements": 1,
        "store_receipts": 1,
        "live_links": 1168,
        "store_outbox": 1168,
        "projection_pending": 0,
        "routes": 9,
        "live_resources": 3,
        "canary": 0,
    }
    if facts != expected:
        raise RuntimeError(f"exact AO terminal Store facts required: {facts}")
    return facts


def inspect(plane):
    profile()
    return snapshot.inspect(plane) | {
        "outcome": "AO_SAVED_SNAPSHOT_INSPECTED",
        "terminalFacts": terminal_facts(),
        "sourceReads": 0,
    }


def disable(plane):
    profile()
    facts = require_terminal_facts()
    value = snapshot.disable(plane)
    return {
        **value,
        "outcome": "AO_SAVED_SNAPSHOT_COMPLETE_DISABLED",
        "terminalFacts": facts,
        "sourceReads": 0,
    }


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
