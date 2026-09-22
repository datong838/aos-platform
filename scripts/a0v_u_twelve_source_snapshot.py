#!/usr/bin/env python3
"""Build one current-U twelve-source group through governed schedule workers."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid5

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import a0v_q_advisor_baseline as baseline
import a0v_snapshot_current_controls as preview
import a0v_u_successor_business as current
from a0v_qyh_current_product_event_first_chain import api, freeze, freeze_or_match


STATE = baseline.STATE / "u-twelve-source-snapshot-v1"
ACTOR = baseline.ACTOR
DEFINITION_ID = str(uuid5(UUID("2d5f282a-6238-4ff2-a05d-ec54ca148ad6"), current.U_ID))
PREDECESSOR_DEFINITION_ID = "ece2c4cb-743e-56ab-b1d7-41055e606136"
CONTROL_PREFIX = "a0v-u-snapshot"
DISABLE_KEY = "a0v-u-twelve-source-disable-complete-v1"


def wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def load(name):
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(_plane):
    preview.INSTALLATION = current.U_ID
    preview.GENERATION = current.U_GENERATION
    result = preview.preflight()
    if (
        len(result["members"]) != 12
        or result["installationRef"]["installationId"] != current.U_ID
        or result["generation"] != current.U_GENERATION
        or result["enabled"] is not False
        or any(member["draft"]["executionEpoch"] != 3 for member in result["members"])
    ):
        raise RuntimeError("exact disabled current-U twelve-source preview required")
    return {"outcome": "U_TWELVE_SOURCE_PREPARED", **result}


def schedule_ingest(_plane):
    prepared = load("prepare")
    results = []
    for member in prepared["members"]:
        pipeline, schedule_id = member["pipelineId"], member["scheduleId"]
        desired = {"enabled": False, "ingest": {"kind": "pipeline-live-v1", "pipelineId": pipeline}}
        intent = STATE / "schedule-intents" / f"{pipeline}.json"
        freeze_or_match(intent, {"scheduleId": schedule_id, "patch": desired})
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
    return {"outcome": "U_TWELVE_SOURCE_SCHEDULES_DISABLED_AND_LIVE", "members": results}


def controls(plane):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner, decode_binding
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.tenant_scope import TenantScope

    load("schedule-ingest")
    prepared = load("prepare")
    scope = TenantScope(**baseline.SCOPE)
    services = plane.pipeline_control_factory.build(scope)
    results = []
    for member in prepared["members"]:
        pipeline, schedule_id, draft = member["pipelineId"], member["scheduleId"], member["draft"]
        prefix = f"{CONTROL_PREFIX}-{pipeline.lower()}"
        overall_intent = STATE / "control-intents" / f"{pipeline}.json"

        def read_rows():
            with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
                selection_row = conn.execute(
                    """SELECT * FROM pipeline_source_selection_revision
                        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                          AND idempotency_key=%s""",
                    (*scope.key, current.U_ID, current.U_GENERATION, prefix + "-selection-v1"),
                ).fetchone()
                control_row = conn.execute(
                    """SELECT * FROM pipeline_runtime_control_revision
                        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                          AND idempotency_key=%s""",
                    (*scope.key, current.U_ID, current.U_GENERATION, prefix + "-control-v1"),
                ).fetchone()
                binding_row = conn.execute(
                    """SELECT * FROM pipeline_schedule_control_binding
                        WHERE org_id=%s AND project_id=%s AND schedule_id=%s AND idempotency_key=%s""",
                    (*scope.key, schedule_id, prefix + "-binding-v1"),
                ).fetchone()
                latest_selection = conn.execute(
                    """SELECT * FROM pipeline_source_selection_revision
                        WHERE org_id=%s AND project_id=%s AND installation_id=%s
                          AND generation=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1""",
                    (*scope.key, current.U_ID, current.U_GENERATION, pipeline),
                ).fetchone()
                latest_control = conn.execute(
                    """SELECT * FROM pipeline_runtime_control_revision
                        WHERE org_id=%s AND project_id=%s AND installation_id=%s
                          AND generation=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1""",
                    (*scope.key, current.U_ID, current.U_GENERATION, pipeline),
                ).fetchone()
                latest_binding = PipelineScheduleControlOwner.read_latest(conn, scope=scope, schedule_id=schedule_id)
            return selection_row, control_row, binding_row, latest_selection, latest_control, latest_binding

        rows = read_rows()
        if not overall_intent.exists() and (rows[3] is not None or rows[4] is not None):
            raise RuntimeError("fresh U source authority required")
        previous_binding = None if rows[5] is None else wire(rows[5].ref)
        freeze_or_match(overall_intent, {
            "pipelineId": pipeline, "scheduleId": schedule_id, "draft": draft,
            "previousBindingRef": previous_binding,
        })

        selection_ref = preview.confirm_once(
            STATE / "selection-intents" / f"{pipeline}.json",
            {"draft": draft, "idempotencyKey": prefix + "-selection-v1", "previousRef": None},
            submit=lambda: services.approve_selection(
                draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft)), actor=ACTOR,
                idempotency_key=prefix + "-selection-v1", previous_ref=None),
            read=lambda: None if (row := read_rows()[0]) is None else decode_selection_row(row).ref,
        )
        control_draft = {
            **draft,
            "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
            "sourceSelectionRef": wire(selection_ref),
        }
        control_ref = preview.confirm_once(
            STATE / "control-approval-intents" / f"{pipeline}.json",
            {"draft": control_draft, "idempotencyKey": prefix + "-control-v1", "previousRef": None},
            submit=lambda: services.approve_control(
                draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(control_draft)), actor=ACTOR,
                idempotency_key=prefix + "-control-v1", previous_ref=None),
            read=lambda: None if (row := read_rows()[1]) is None else decode_control_row(row).ref,
        )
        binding_ref = preview.confirm_once(
            STATE / "binding-intents" / f"{pipeline}.json",
            {"pipelineId": pipeline, "scheduleId": schedule_id, "controlRef": wire(control_ref),
             "idempotencyKey": prefix + "-binding-v1", "previousRef": previous_binding},
            submit=lambda: services.bind_schedule(
                pipeline_id=pipeline, schedule_id=schedule_id, control_ref=control_ref, actor=ACTOR,
                idempotency_key=prefix + "-binding-v1", previous_ref=previous_binding),
            read=lambda: None if (row := read_rows()[2]) is None else decode_binding(row).ref,
        )
        results.append(
            {
                "pipelineId": pipeline,
                "scheduleId": schedule_id,
                "selectionRef": wire(selection_ref),
                "controlRef": wire(control_ref),
                "bindingRef": wire(binding_ref),
            }
        )
    return {"outcome": "U_TWELVE_SOURCE_CONTROLS_CURRENT", "members": results}


def configure(plane):
    from aos_api.tenant_scope import TenantScope

    released = load("release-predecessor")
    if released["definition"]["body"]["state"] != "retired":
        raise RuntimeError("released predecessor definition retirement required")
    controlled = load("controls")
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    options = service.options(actor=ACTOR, installation_id=current.U_ID, generation=current.U_GENERATION)
    if options.get("status") != "ready" or len(options.get("members", [])) != 12 or not options.get("policies"):
        raise RuntimeError("current-U twelve-source options are not ready")
    confirmed = {item["scheduleId"]: item for item in controlled["members"]}
    members = [{"scheduleId": item["scheduleId"], "bindingRef": item["bindingRef"]} for item in options["members"]]
    if any(confirmed.get(item["scheduleId"], {}).get("bindingRef") != item["bindingRef"] for item in members):
        raise RuntimeError("snapshot options differ from freshly confirmed U bindings")
    result = service.configure(
        definition_id=DEFINITION_ID,
        actor=ACTOR,
        cron="* * * * *",
        policy_ref=options["policies"][0],
        members=members,
        expected_ref=None,
        idempotency_key="a0v-u-twelve-source-definition-v1",
    )
    return {"outcome": "U_TWELVE_SOURCE_DEFINITION_DISABLED", "options": options, "definition": result}


def release_predecessor(plane):
    """Retire the disabled definition left by the formally uninstalled S installation."""
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(**baseline.SCOPE)
    service = plane.pipeline_control_factory.build_snapshot_schedule(scope, source_controls=True)
    with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
        current_definition = service._owner.read(
            conn, scope=scope, definition_id=PREDECESSOR_DEFINITION_ID)
    if (current_definition is None or current_definition["body"]["state"] != "disabled"
            or current_definition["body"]["installationId"] == current.U_ID):
        raise RuntimeError("exact disabled released predecessor definition required")
    result = service.transition(
        definition_id=PREDECESSOR_DEFINITION_ID, actor=ACTOR, intent="retire",
        expected_ref=current_definition["ref"],
        idempotency_key="a0v-u-twelve-source-retire-released-s-definition-v1",
    )
    return {"outcome": "RELEASED_PREDECESSOR_DEFINITION_RETIRED", "definition": result}


def enable(plane):
    from aos_api.tenant_scope import TenantScope

    configured = load("configure")["definition"]
    if configured["body"]["state"] != "disabled":
        raise RuntimeError("disabled U definition predecessor required")
    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    result = service.transition(
        definition_id=DEFINITION_ID,
        actor=ACTOR,
        intent="enable",
        expected_ref=configured["ref"],
        idempotency_key="a0v-u-twelve-source-enable-v1",
    )
    return {"outcome": "U_TWELVE_SOURCE_DEFINITION_ENABLED", "definition": result, "enabledAt": datetime.now(timezone.utc).isoformat()}


def inspect(plane):
    from aos_api.tenant_scope import TenantScope

    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    return {"outcome": "U_TWELVE_SOURCE_INSPECTED", "runtime": service.read_runtime_status(
        definition_id=DEFINITION_ID, actor=ACTOR), "observedAt": datetime.now(timezone.utc).isoformat()}


def recover_saved(plane):
    """Renew authority for the original saved input; never perform another source read."""
    from aos_api.tenant_scope import TenantScope

    service = plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope(**baseline.SCOPE), source_controls=True)
    context = service.read_recovery_context(group_id="c5ff1926-45b0-56de-b6b3-07d5b7d053a1", actor=ACTOR)
    now = datetime.fromisoformat(context["windowRules"]["currentTime"])
    result = service.renew_saved_group(
        group_id=context["groupId"], actor=ACTOR,
        expected_definition_ref=context["expectedDefinitionRef"],
        expected_recovery_ref=context["expectedRecoveryRef"],
        input_manifest_hash=context["inputManifestHash"],
        not_before=now, expires_at=now + timedelta(hours=6),
        idempotency_key="a0v-u-twelve-source-saved-input-recovery-v1",
    )
    return {"outcome": "U_TWELVE_SOURCE_SAVED_INPUT_RECOVERY_APPROVED",
            "context": context, "recovery": result, "sourceReads": 0}


def pause_recovery(plane):
    """Freeze scheduling after a released runtime; preserve the one saved-input group."""
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(**baseline.SCOPE)
    service = plane.pipeline_control_factory.build_snapshot_schedule(scope, source_controls=True)
    status = service.read_runtime_status(definition_id=DEFINITION_ID, actor=ACTOR)
    if status.get("configurationState") != "enabled":
        raise RuntimeError("enabled U recovery definition required before pause")
    with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
        facts = conn.execute(
            """SELECT
              (SELECT count(*) FROM pipeline_snapshot_schedule_member
                WHERE org_id=%s AND project_id=%s AND group_id=%s) members,
              (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
                ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
                WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
                  AND r.status='running' AND r.executor_stopped IS FALSE) running,
              (SELECT count(*) FROM pipeline_snapshot_group_input
                WHERE org_id=%s AND project_id=%s AND group_id=%s
                  AND manifest_hash=%s) saved_input,
              (SELECT count(*) FROM pipeline_snapshot_group_recovery_receipt
                WHERE org_id=%s AND project_id=%s AND group_id=%s) recoveries,
              (SELECT count(*) FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                  AND enabled IS FALSE AND operation_fence IS TRUE
                  AND observed_state='unknown') fenced_binding,
              (SELECT count(*) FROM extension_runtime_resource_lease
                WHERE org_id=%s AND project_id=%s AND generation=%s
                  AND cleanup_state='released' AND observed_release IS TRUE) released_resources""",
            (*scope.key, "c5ff1926-45b0-56de-b6b3-07d5b7d053a1",
             *scope.key, "c5ff1926-45b0-56de-b6b3-07d5b7d053a1",
             *scope.key, "c5ff1926-45b0-56de-b6b3-07d5b7d053a1",
             "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01",
             *scope.key, "c5ff1926-45b0-56de-b6b3-07d5b7d053a1",
             *scope.key, current.U_ID, current.U_GENERATION,
             *scope.key, current.U_GENERATION),
        ).fetchone()
    expected = {"members": 12, "running": 12, "saved_input": 1,
                "recoveries": 1, "fenced_binding": 1, "released_resources": 3}
    if dict(facts) != expected:
        raise RuntimeError("exact released U saved-input recovery facts required")
    result = service.transition(
        definition_id=DEFINITION_ID, actor=ACTOR, intent="disable",
        expected_ref=status["definitionRef"],
        idempotency_key="a0v-u-twelve-source-pause-released-recovery-v1",
    )
    return {"outcome": "U_TWELVE_SOURCE_RELEASED_RECOVERY_PAUSED",
            "facts": expected, "definition": result, "sourceReads": 0}


def disable(plane):
    from aos_api.tenant_scope import TenantScope

    service = plane.pipeline_control_factory.build_snapshot_schedule(TenantScope(**baseline.SCOPE), source_controls=True)
    status = service.read_runtime_status(definition_id=DEFINITION_ID, actor=ACTOR)
    definition_ref = status["definitionRef"]
    if status.get("configurationState") != "enabled":
        raise RuntimeError("current recovered U definition must still be enabled before disable")
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
        groups = conn.execute(
            """SELECT c.group_id, count(r.id) FILTER (WHERE r.status='succeeded'
                         AND r.executor_id='ec-live-v1' AND r.executor_stopped IS TRUE
                         AND r.finished_at IS NOT NULL) AS succeeded_members,
                      count(i.group_id) AS saved_inputs
                 FROM pipeline_snapshot_schedule_claim c
                 JOIN pipeline_snapshot_schedule_member m USING(org_id,project_id,group_id)
                 JOIN meta_schedule_run r ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
                 LEFT JOIN pipeline_snapshot_group_input i USING(org_id,project_id,group_id)
                WHERE c.org_id=%s AND c.project_id=%s
                  AND c.request->'definitionRef'->>'resourceId'=%s
                GROUP BY c.group_id ORDER BY c.group_id""",
            (*baseline.SCOPE.values(), definition_ref["resourceId"]),
        ).fetchall()
    if len(groups) != 1 or groups[0]["succeeded_members"] != 12 or groups[0]["saved_inputs"] != 12:
        raise RuntimeError("one complete U twelve-source group required before disable")
    result = service.transition(
        definition_id=DEFINITION_ID,
        actor=ACTOR,
        intent="disable",
        expected_ref=definition_ref,
        idempotency_key=DISABLE_KEY,
    )
    return {"outcome": "U_TWELVE_SOURCE_COMPLETE_GROUP_DISABLED", "runtime": status,
            "group": {"groupId": str(groups[0]["group_id"]), "succeededMembers": 12,
                      "savedInputJoins": groups[0]["saved_inputs"]}, "definition": result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "schedule-ingest", "controls", "release-predecessor",
                                            "configure", "enable", "inspect", "recover-saved",
                                            "pause-recovery", "disable"))
    args = parser.parse_args()
    _previous, _preflight, plane = baseline.setup()
    result = globals()[args.action.replace("-", "_")](plane)
    if args.action != "inspect":
        output = STATE / f"{args.action}-result.json"
        if output.exists():
            raise RuntimeError(f"immutable {args.action} output exists")
        freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
