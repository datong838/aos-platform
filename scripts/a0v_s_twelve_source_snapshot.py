#!/usr/bin/env python3
"""Build one current-S twelve-source snapshot group through governed services."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID, uuid5

import a0v_q_advisor_baseline as baseline
import a0v_s_successor_business as current
import a0v_snapshot_current_controls as legacy_preview
from a0v_qyh_current_product_event_first_chain import api, freeze, freeze_or_match


STATE = baseline.STATE / "s-twelve-source-snapshot-v1"
ACTOR = baseline.ACTOR
DEFINITION_ID = str(uuid5(UUID("2d5f282a-6238-4ff2-a05d-ec54ca148ad6"), current.S_ID))
P02 = "P02-product-qyh"


def _wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _load(name):
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(_plane):
    legacy_preview.INSTALLATION = current.S_ID
    legacy_preview.GENERATION = current.S_GENERATION
    result = legacy_preview.preflight()
    if (len(result["members"]) != 12 or result["installationRef"]["installationId"] != current.S_ID
            or result["generation"] != current.S_GENERATION or result["enabled"] is not False):
        raise RuntimeError("exact disabled current-S twelve-source preview required")
    return {"outcome": "S_TWELVE_SOURCE_PREPARED", **result}


def schedule_ingest(_plane):
    prepared = _load("prepare")
    results = []
    for member in prepared["members"]:
        pipeline, schedule_id = member["pipelineId"], member["scheduleId"]
        desired = {"enabled": False, "ingest": {"kind": "pipeline-live-v1", "pipelineId": pipeline}}
        intent_path = STATE / "schedule-intents" / f"{pipeline}.json"
        freeze_or_match(intent_path, {"scheduleId": schedule_id, "patch": desired})
        status, observed = api("GET", f"/v1/schedules/{schedule_id}")
        if status != 200:
            raise RuntimeError(f"schedule {schedule_id} unavailable")
        matches = observed.get("enabled") is False and observed.get("ingest") == desired["ingest"]
        if not matches:
            marker = STATE / "schedule-results" / f"{pipeline}.json"
            if marker.exists():
                raise RuntimeError(f"schedule {schedule_id} drifted after confirmed patch")
            try:
                api("PATCH", f"/v1/schedules/{schedule_id}", desired)
            except Exception:
                pass
            status, observed = api("GET", f"/v1/schedules/{schedule_id}")
            if status != 200 or observed.get("enabled") is not False or observed.get("ingest") != desired["ingest"]:
                raise RuntimeError(f"schedule {schedule_id} patch unconfirmed; no resend")
            freeze(marker, {"scheduleId": schedule_id, "confirmed": True})
        results.append({"pipelineId": pipeline, "scheduleId": schedule_id, "confirmed": True})
    return {"outcome": "S_TWELVE_SOURCE_SCHEDULES_DISABLED_AND_LIVE", "members": results}


def controls(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.tenant_scope import TenantScope

    _load("schedule-ingest")
    prepared = _load("prepare")
    scope = TenantScope(**baseline.SCOPE)
    services = plane.pipeline_control_factory.build(scope)
    results = []
    for member in prepared["members"]:
        pipeline, schedule_id = member["pipelineId"], member["scheduleId"]
        with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
            selection_row = conn.execute("""SELECT * FROM pipeline_source_selection_revision
              WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
              ORDER BY revision DESC LIMIT 1""", (*scope.key, current.S_ID, current.S_GENERATION, pipeline)).fetchone()
            control_row = conn.execute("""SELECT * FROM pipeline_runtime_control_revision
              WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
              ORDER BY revision DESC LIMIT 1""", (*scope.key, current.S_ID, current.S_GENERATION, pipeline)).fetchone()
            binding = PipelineScheduleControlOwner.read_latest(conn, scope=scope, schedule_id=schedule_id)
        if pipeline == P02:
            if (selection_row is None or control_row is None or binding is None
                    or binding.installation_id != current.S_ID or binding.generation != current.S_GENERATION):
                raise RuntimeError("existing governed S Product control required")
            selection_ref, control_ref = _wire(decode_selection_row(selection_row).ref), _wire(decode_control_row(control_row).ref)
            if _wire(binding.control_ref) != control_ref:
                raise RuntimeError("S Product binding/control differs")
            results.append({"pipelineId": pipeline, "scheduleId": schedule_id, "reused": True,
                            "selectionRef": selection_ref, "controlRef": control_ref, "bindingRef": _wire(binding.ref)})
            continue
        draft = member["draft"]
        selection_ref = services.approve_selection(
            draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft)), actor=ACTOR,
            idempotency_key=f"a0v-s-snapshot-{pipeline.lower()}-selection-v1",
            previous_ref=None if selection_row is None else _wire(decode_selection_row(selection_row).ref))
        control_draft = {**draft, "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
                         "sourceSelectionRef": _wire(selection_ref)}
        control_ref = services.approve_control(
            draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(control_draft)), actor=ACTOR,
            idempotency_key=f"a0v-s-snapshot-{pipeline.lower()}-control-v1",
            previous_ref=None if control_row is None else _wire(decode_control_row(control_row).ref))
        binding_ref = services.bind_schedule(
            pipeline_id=pipeline, schedule_id=schedule_id, control_ref=control_ref, actor=ACTOR,
            idempotency_key=f"a0v-s-snapshot-{pipeline.lower()}-binding-v1",
            previous_ref=None if binding is None else _wire(binding.ref))
        results.append({"pipelineId": pipeline, "scheduleId": schedule_id, "reused": False,
                        "selectionRef": _wire(selection_ref), "controlRef": _wire(control_ref),
                        "bindingRef": _wire(binding_ref)})
    return {"outcome": "S_TWELVE_SOURCE_CONTROLS_CURRENT", "members": results}


def configure(plane):
    from aos_api.tenant_scope import TenantScope
    controlled = _load("controls")
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    options = service.options(actor=ACTOR, installation_id=current.S_ID, generation=current.S_GENERATION)
    if options.get("status") != "ready" or len(options.get("members", [])) != 12 or not options.get("policies"):
        raise RuntimeError("current-S twelve-source options are not ready")
    by_schedule = {item["scheduleId"]: item for item in controlled["members"]}
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]}
               for item in options["members"]]
    if any(by_schedule.get(item["scheduleId"], {}).get("bindingRef") != item["bindingRef"] for item in members):
        raise RuntimeError("snapshot options differ from freshly confirmed bindings")
    result = service.configure(definition_id=DEFINITION_ID, actor=ACTOR, cron="0 * * * *",
        policy_ref=options["policies"][0], members=members, expected_ref=None,
        idempotency_key="a0v-s-twelve-source-definition-v1")
    return {"outcome": "S_TWELVE_SOURCE_DEFINITION_DISABLED", "options": options,
            "definition": result}


def enable(plane):
    from aos_api.tenant_scope import TenantScope
    configured = _load("configure")["definition"]
    if configured["body"]["state"] != "disabled":
        raise RuntimeError("disabled predecessor required")
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    result = service.transition(definition_id=DEFINITION_ID, actor=ACTOR, intent="enable",
        expected_ref=configured["ref"], idempotency_key="a0v-s-twelve-source-enable-v1")
    return {"outcome": "S_TWELVE_SOURCE_DEFINITION_ENABLED", "definition": result,
            "enabledAt": datetime.now(timezone.utc).isoformat()}


def observe(plane):
    from aos_api.tenant_scope import TenantScope
    _load("enable")
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    result = service.read_runtime_status(definition_id=DEFINITION_ID, actor=ACTOR)
    return {"outcome": "S_TWELVE_SOURCE_OBSERVED", "runtime": result,
            "observedAt": datetime.now(timezone.utc).isoformat()}


def reschedule_minute(plane):
    """Short-lived acceptance cadence; each transition has its own Receipt key."""
    from aos_api.tenant_scope import TenantScope
    configured = _load("configure")
    enabled = _load("enable")["definition"]
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    disabled = service.transition(definition_id=DEFINITION_ID, actor=ACTOR, intent="disable",
        expected_ref=enabled["ref"], idempotency_key="a0v-s-twelve-source-disable-hourly-v1")
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]}
               for item in configured["options"]["members"]]
    minute = service.configure(definition_id=DEFINITION_ID, actor=ACTOR, cron="* * * * *",
        policy_ref=configured["options"]["policies"][0], members=members,
        expected_ref=disabled["ref"], idempotency_key="a0v-s-twelve-source-minute-v1")
    active = service.transition(definition_id=DEFINITION_ID, actor=ACTOR, intent="enable",
        expected_ref=minute["ref"], idempotency_key="a0v-s-twelve-source-enable-minute-v1")
    return {"outcome": "S_TWELVE_SOURCE_MINUTE_ACCEPTANCE_ENABLED", "disabled": disabled,
            "configured": minute, "definition": active}


def disable_pending(plane):
    from aos_api.tenant_scope import TenantScope
    current_definition = _load("reschedule-minute")["definition"]
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    result = service.transition(definition_id=DEFINITION_ID, actor=ACTOR, intent="disable",
        expected_ref=current_definition["ref"], idempotency_key="a0v-s-twelve-source-disable-pending-v1")
    return {"outcome": "S_TWELVE_SOURCE_PENDING_GROUP_DISABLED", "definition": result}


def renew_product(plane):
    """Renew only P02 after its previous one-call budget was consumed."""
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.tenant_scope import TenantScope

    closure = json.loads((baseline.ROOT.parent /
        ".aos-recovery-20260917/state/q-advisor-baseline/snapshot-group-closure/audit.json"
    ).read_text(encoding="utf-8"))
    if closure.get("outcome") != "S_SNAPSHOT_GROUP_UNACCEPTED_CLOSURE_GREEN":
        raise RuntimeError("formal no-effect group closure required")
    prepared = _load("prepare")
    product = next(item for item in prepared["members"] if item["pipelineId"] == P02)
    scope = TenantScope(**baseline.SCOPE)
    services = plane.pipeline_control_factory.build(scope)
    with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
        selection_row = conn.execute("""SELECT * FROM pipeline_source_selection_revision
          WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
          ORDER BY revision DESC LIMIT 1""", (*scope.key, current.S_ID, current.S_GENERATION, P02)).fetchone()
        control_row = conn.execute("""SELECT * FROM pipeline_runtime_control_revision
          WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
          ORDER BY revision DESC LIMIT 1""", (*scope.key, current.S_ID, current.S_GENERATION, P02)).fetchone()
        binding = PipelineScheduleControlOwner.read_latest(conn, scope=scope, schedule_id=product["scheduleId"])
        consumed = conn.execute("""SELECT count(*) AS n FROM pipeline_controlled_source_claim
          WHERE org_id=%s AND project_id=%s AND control_id=%s AND control_revision=%s""",
          (*scope.key, control_row["control_id"], control_row["revision"])).fetchone()["n"]
    if selection_row is None or control_row is None or binding is None or consumed != 1:
        raise RuntimeError("exact consumed P02 predecessor required")
    selection_previous = _wire(decode_selection_row(selection_row).ref)
    control_previous = _wire(decode_control_row(control_row).ref)
    if _wire(binding.control_ref) != control_previous:
        raise RuntimeError("P02 binding predecessor differs")
    draft = product["draft"]
    selection_ref = services.approve_selection(
        draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft)), actor=ACTOR,
        idempotency_key="a0v-s-snapshot-p02-product-qyh-selection-v2", previous_ref=selection_previous)
    control_draft = {**draft, "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
                     "sourceSelectionRef": _wire(selection_ref)}
    control_ref = services.approve_control(
        draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(control_draft)), actor=ACTOR,
        idempotency_key="a0v-s-snapshot-p02-product-qyh-control-v2", previous_ref=control_previous)
    binding_ref = services.bind_schedule(
        pipeline_id=P02, schedule_id=product["scheduleId"], control_ref=control_ref, actor=ACTOR,
        idempotency_key="a0v-s-snapshot-p02-product-qyh-binding-v2", previous_ref=_wire(binding.ref))
    return {"outcome": "S_PRODUCT_SOURCE_BUDGET_RENEWED", "consumedPredecessorClaims": consumed,
            "selectionRef": _wire(selection_ref), "controlRef": _wire(control_ref),
            "bindingRef": _wire(binding_ref)}


def configure_retry(plane):
    from aos_api.tenant_scope import TenantScope
    renewed = _load("renew-product")
    disabled = _load("disable-pending")["definition"]
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    options = service.options(actor=ACTOR, installation_id=current.S_ID, generation=current.S_GENERATION)
    if options.get("status") != "ready" or len(options.get("members", [])) != 12:
        raise RuntimeError("renewed twelve-source options required")
    product = next(item for item in options["members"] if item["pipelineId"] == P02)
    if product["bindingRef"] != renewed["bindingRef"]:
        raise RuntimeError("renewed P02 binding not visible in options")
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]}
               for item in options["members"]]
    result = service.configure(definition_id=DEFINITION_ID, actor=ACTOR, cron="* * * * *",
        policy_ref=options["policies"][0], members=members, expected_ref=disabled["ref"],
        idempotency_key="a0v-s-twelve-source-minute-retry-v2")
    return {"outcome": "S_TWELVE_SOURCE_RETRY_CONFIGURED", "options": options, "definition": result}


def enable_retry(plane):
    from aos_api.tenant_scope import TenantScope
    configured = _load("configure-retry")["definition"]
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    result = service.transition(definition_id=DEFINITION_ID, actor=ACTOR, intent="enable",
        expected_ref=configured["ref"], idempotency_key="a0v-s-twelve-source-enable-retry-v2")
    return {"outcome": "S_TWELVE_SOURCE_RETRY_ENABLED", "definition": result,
            "enabledAt": datetime.now(timezone.utc).isoformat()}


def disable_retry(plane):
    from aos_api.tenant_scope import TenantScope
    enabled = _load("enable-retry")["definition"]
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    result = service.transition(definition_id=DEFINITION_ID, actor=ACTOR, intent="disable",
        expected_ref=enabled["ref"], idempotency_key="a0v-s-twelve-source-disable-retry-v2")
    return {"outcome": "S_TWELVE_SOURCE_RETRY_DISABLED", "definition": result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "schedule-ingest", "controls", "configure", "enable",
                                           "reschedule-minute", "disable-pending", "renew-product",
                                           "configure-retry", "enable-retry", "disable-retry", "observe"))
    args = parser.parse_args()
    output = STATE / f"{args.action}-result.json"
    if output.exists():
        raise RuntimeError(f"immutable {args.action} output exists")
    _previous, _preflight, plane = baseline.setup()
    result = globals()[args.action.replace("-", "_")](plane)
    freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
