#!/usr/bin/env python3
"""W5: rebuild the snapshot schedule definition bound to the DS installation.

Adapted from the W4 rebuild (a0v_w4_definition_rebuild.py) with the root-cause
fix: CRON is a SAFE staggered value instead of "* * * * *".

Root cause (closed this wave): W4's every-minute cron + 15s worker tick meant
the first tick after enable dispatched all 12 pipelines concurrently; on the
2CPU/3GB colima host the lease-renewal loop starved (last renew 02:39:05,
dispatch 02:39:44, timer 02:44:05) and the Host took the SAFE_BLOCKED exit.
The definition-level cron is a single value (per-member stagger is an open
architecture gap), so the safe value is a DAILY slot in the low-usage window:
04:00 UTC (12:00 Beijing) — one group per day, far from the W4 crash pattern.

Phases:
  verify    - read-only: definition heads + runtime status
  controls  - clone the 12 selection->control->binding chains to DS facts
  retire    - retire the DR-bound definition 446cc1ae (frees occupancy)
  configure - create the NEW definition (new UUID) with the safe cron
  enable    - enable the new definition (flips the 12 meta_schedule rows)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w5-definition-rebuild"
# The DR-bound definition (W4 rebuild's output) to retire
OLD_DEFINITION = "446cc1ae-fa5b-406a-9446-d32104126dda"
# The NEW definition id for DS (generated fresh)
DEFINITION = "8b1d0f7e-3a6c-4b58-9d27-6f0e2a91c001"
DS_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"
DS_GENERATION = "b59582cc-2abf-472d-8f59-bfc8be1138c8"
SOURCE_ID = "d2d3c478-f9d9-4489-92b7-1de57f546452"
SOURCE_GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
# SAFE: daily at 04:00 UTC (12:00 Beijing) — replaces the fatal "* * * * *"
CRON = "0 4 * * *"
KEY = "a0v-w5-ds-definition-rebuild-20260923"
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"


def _configure():
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(BASE / "bm-runtime-credentials/runtime-host-identities.json"),
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_BUNDLE_ROOT": str(BASE / "bn-canonical-alias-registry/signed-bundles"),
        "AOS_BUNDLE_TRUST_ROOTS_FILE": str(BASE / "bm-trust-root-rotation/signing/trust-roots.json"),
        "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(BASE / "bn-registration-credentials/registration-main-identity.json"),
    })
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    sys.path.insert(0, str(ROOT / "scripts"))


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(name):
    path = STATE / f"{name}.json"
    if not path.is_file():
        raise RuntimeError(f"frozen {name} required (run earlier phases first)")
    return json.loads(path.read_text(encoding="utf-8"))


def _service():
    _configure()
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.tenant_scope import TenantScope
    plane = build_runtime_control_plane(registration_connect=registration_connection)
    return plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)


def _head_ref(definition_id=DEFINITION):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn:
        row = conn.execute("""SELECT revision, state, content_hash FROM pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
            ("org-org", "dev-project", definition_id)).fetchone()
    if row is None:
        return None
    return dict(revision=row["revision"], state=row["state"],
                ref=dict(resourceType="SnapshotScheduleDefinitionRevision",
                         resourceId="snapshot-schedule-" + definition_id,
                         revision=row["revision"], contentHash=row["content_hash"]))


def verify():
    _configure()
    service = _service()
    status = service.read_runtime_status(definition_id=OLD_DEFINITION, actor=ACTOR)
    return {"outcome": "W5_DS_DEFINITION_VERIFY", "oldHead": _head_ref(OLD_DEFINITION),
            "newHead": _head_ref(), "runtimeStatus": status}


def _wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _plane():
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection)


def controls():
    """Clone the twelve selection->control->binding chains onto DS facts."""
    from datetime import timedelta
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ec_ingress_journal import _digest
    from aos_api.tenant_scope import TenantScope

    _configure()
    scope = TenantScope("org-org", "dev-project")
    plane_services = _plane().pipeline_control_factory.build(scope)
    workers = dict(org_id="org-org", project_id="dev-project")
    with consumer_connection(runtime_worker_connection, workers) as conn:
        head = conn.execute("""SELECT i.current_revision, r.state, r.lock_hash, r.overlay_revision
            FROM bundle_installation i JOIN bundle_installation_revision r
            ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=
               (r.org_id,r.project_id,r.installation_pk,r.revision)
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s
            LIMIT 1""", (*scope.key, DS_ID)).fetchone()
        if head is None or head["state"] != "active":
            raise RuntimeError(f"DS installation head unavailable: {dict(head) if head else None}")
        ref = CurrentInstallationRef.model_validate(dict(
            installationId=DS_ID, revision=head["current_revision"],
            lockHash=head["lock_hash"], overlayRevision=head["overlay_revision"]))
        binding = conn.execute("""SELECT config_ref, execution_epoch FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            ORDER BY revision DESC LIMIT 1""", (*scope.key, DS_ID, DS_GENERATION)).fetchone()
        if binding is None or binding["config_ref"].get("revision") != 1:
            raise RuntimeError(f"extension binding config rev1 required: {dict(binding) if binding else None}")
        config_ref, epoch = binding["config_ref"], int(binding["execution_epoch"])
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        pipelines = [r["pipeline_id"] for r in conn.execute(
            """SELECT DISTINCT pipeline_id FROM pipeline_source_selection_revision
               WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
               ORDER BY pipeline_id""", (*scope.key, SOURCE_ID, SOURCE_GENERATION)).fetchall()]
        if len(pipelines) != 12:
            raise RuntimeError(f"twelve source pipelines required: {len(pipelines)}")
        members = []
        for pipeline in pipelines:
            selection_row = conn.execute("""SELECT * FROM pipeline_source_selection_revision
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                ORDER BY revision DESC LIMIT 1""", (*scope.key, SOURCE_ID, SOURCE_GENERATION, pipeline)).fetchone()
            control_row = conn.execute("""SELECT * FROM pipeline_runtime_control_revision
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                ORDER BY revision DESC LIMIT 1""", (*scope.key, SOURCE_ID, SOURCE_GENERATION, pipeline)).fetchone()
            schedules = conn.execute("""SELECT id, enabled FROM meta_schedule
                WHERE org_id=%s AND project_id=%s AND pipeline_id=%s""",
                (*scope.key, pipeline)).fetchall()
            if selection_row is None or control_row is None or len(schedules) != 1 or schedules[0]["enabled"] is not False:
                raise RuntimeError(f"member {pipeline} facts unavailable")
            schedule_id = schedules[0]["id"]
            saved = decode_selection_row(selection_row)
            control = decode_control_row(control_row)
            schedule_binding = PipelineScheduleControlOwner.read_latest(conn, scope=scope, schedule_id=schedule_id)
            if (_wire(saved.ref) == control.draft.source_selection_ref
                    and schedule_binding is not None and schedule_binding.generation == DS_GENERATION
                    and _wire(control.ref) == _wire(schedule_binding.control_ref)):
                members.append({"pipelineId": pipeline, "scheduleId": schedule_id, "reused": True,
                                "selectionRef": _wire(saved.ref), "controlRef": _wire(control.ref),
                                "bindingRef": _wire(schedule_binding.ref)})
                continue
            draft = saved.draft.model_dump(mode="json", by_alias=True, exclude_none=True)
            draft.update({"installationRef": _wire(ref), "generation": DS_GENERATION,
                          "executionEpoch": epoch,
                          "configurationRef": config_ref,
                          "notBefore": now.isoformat(), "expiresAt": (now + timedelta(hours=6)).isoformat()})
            # If DS already has a resumable selection for this pipeline, reuse its ref
            ds_latest = conn.execute("""SELECT * FROM pipeline_source_selection_revision
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                ORDER BY revision DESC LIMIT 1""", (*scope.key, DS_ID, DS_GENERATION, pipeline)).fetchone()
            if ds_latest is not None:
                latest_saved = decode_selection_row(ds_latest)
                latest_draft = latest_saved.draft.model_dump(mode="json", by_alias=True, exclude_none=True)
                resume = {k: latest_draft.get(k) for k in ("sourceId", "graphRevision", "graphHash", "sourceConfigurationRef")}
                if all(latest_draft.get(k) == draft.get(k) for k in resume):
                    members.append({"pipelineId": pipeline, "scheduleId": schedule_id, "reused": False,
                                    "draft": latest_draft, "resumeSelection": _wire(latest_saved.ref), "previous": {
                                        "selection": _wire(saved.ref), "control": _wire(control.ref),
                                        "binding": _wire(schedule_binding.ref) if schedule_binding else None}})
                    continue
            graph = conn.execute("""SELECT revision, payload FROM phase5_pipeline_graph
                WHERE org_id=%s AND project_id=%s AND pipeline_id=%s""", (*scope.key, pipeline)).fetchone()
            if graph is None or graph["revision"] != draft["graphRevision"] or _digest(graph["payload"]) != draft["graphHash"]:
                raise RuntimeError(f"member {pipeline} graph drift")
            source = SourceConfigurationRevisionStore(HostTransaction(conn), scope).read_current(draft["sourceId"])
            if source is None or json.dumps(_wire(source.ref), sort_keys=True) != json.dumps(draft["sourceConfigurationRef"], sort_keys=True):
                raise RuntimeError(f"member {pipeline} source configuration drift")
            members.append({"pipelineId": pipeline, "scheduleId": schedule_id, "reused": False,
                            "draft": draft, "previous": {
                                "selection": _wire(saved.ref), "control": _wire(control.ref),
                                "binding": _wire(schedule_binding.ref) if schedule_binding else None}})
        from psycopg import Rollback
        def _dry(_conn):
            for member in members:
                if member["reused"]:
                    continue
                draft = PipelineSourceSelectionDraft.model_validate_json(json.dumps(member["draft"]))
                plane_services.selections._guarded(_conn, draft, ACTOR, lambda value: True, snapshot=True)
            raise Rollback()
        try:
            _dry(conn)
        except Rollback:
            pass
    results = []
    for member in members:
        pipeline = member["pipelineId"]
        if member["reused"]:
            results.append(member)
            continue
        if member.get("resumeSelection"):
            selection_ref_raw = member["resumeSelection"]
        else:
            selection_ref_raw = _wire(plane_services.approve_selection(
                draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(member["draft"])), actor=ACTOR,
                idempotency_key=f"{KEY}-{pipeline.lower()}-selection-v1", previous_ref=None))
        control_draft = {**member["draft"], "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
                         "sourceSelectionRef": selection_ref_raw}
        control_ref = plane_services.approve_control(
            draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(control_draft)), actor=ACTOR,
            idempotency_key=f"{KEY}-{pipeline.lower()}-control-v1", previous_ref=None)
        binding_ref = plane_services.bind_schedule(
            pipeline_id=pipeline, schedule_id=member["scheduleId"], control_ref=control_ref, actor=ACTOR,
            idempotency_key=f"{KEY}-{pipeline.lower()}-binding-v1",
            previous_ref=member["previous"]["binding"])
        results.append({"pipelineId": pipeline, "scheduleId": member["scheduleId"], "reused": False,
                        "selectionRef": selection_ref_raw, "controlRef": _wire(control_ref),
                        "bindingRef": _wire(binding_ref)})
    frozen = {"configRef": config_ref, "executionEpoch": epoch, "members": results}
    _write("controls", frozen)
    return {"outcome": "W5_DS_CONTROLS_CURRENT", "members": len(results),
            "reused": sum(1 for r in results if r["reused"]), "configRevision": config_ref.get("revision")}


def retire():
    """Retire the disabled DR-bound definition to release schedule occupancy."""
    _configure()
    service = _service()
    head = _head_ref(OLD_DEFINITION)
    if head is None:
        raise RuntimeError("old definition head unavailable")
    if head["state"] == "retired":
        return {"outcome": "W5_OLD_DEFINITION_ALREADY_RETIRED", "head": head}
    if head["state"] != "disabled":
        raise RuntimeError(f"old definition not disabled: {head}")
    result = service.transition(definition_id=OLD_DEFINITION, actor=ACTOR, intent="retire",
        expected_ref=head["ref"], idempotency_key="a0v-w5-retire-old-definition-20260923-v1")
    _write("retire", {"definition": result})
    return {"outcome": "W5_OLD_DEFINITION_RETIRED", "definition": result}


def options():
    _configure()
    service = _service()
    result = service.options(actor=ACTOR, installation_id=DS_ID, generation=DS_GENERATION)
    if result.get("status") != "ready" or len(result.get("members", [])) != 12 or not result.get("policies"):
        raise RuntimeError(f"DS options not ready: status={result.get('status')} missing={result.get('missing')} ambiguous={result.get('ambiguous')}")
    frozen = {"members": result["members"], "policyRef": result["policies"][0],
              "priorHead": _head_ref()}
    _write("options", frozen)
    return {"outcome": "W5_DS_OPTIONS_READY", "members": len(result["members"]),
            "policyRef": result["policies"][0], "priorHead": frozen["priorHead"]}


def configure():
    _configure()
    frozen = _load("options")
    service = _service()
    old_head = _head_ref(OLD_DEFINITION)
    if old_head is None or old_head["state"] != "retired":
        raise RuntimeError(f"old definition must be retired first: {old_head}")
    if _head_ref(DEFINITION) is not None:
        raise RuntimeError("new definition head already exists")
    members = [{"scheduleId": m["scheduleId"], "bindingRef": m["bindingRef"]} for m in frozen["members"]]
    result = service.configure(definition_id=DEFINITION, actor=ACTOR, cron=CRON,
        policy_ref=frozen["policyRef"], members=members, expected_ref=None,
        idempotency_key=f"{KEY}-configure-v1")
    _write("configure", {"definition": result})
    return {"outcome": "W5_DS_DEFINITION_CONFIGURED", "definition": result}


def enable():
    _configure()
    configured = _load("configure")["definition"]
    service = _service()
    head = _head_ref()
    if head is None or head["revision"] != configured["ref"]["revision"] or head["state"] != "disabled":
        raise RuntimeError(f"configure head drift: {head} vs configured rev {configured['ref']['revision']}")
    result = service.transition(definition_id=DEFINITION, actor=ACTOR, intent="enable",
        expected_ref=configured["ref"],
        idempotency_key=f"{KEY}-enable-v1")
    _write("enable", {"definition": result})
    return {"outcome": "W5_DS_DEFINITION_ENABLED", "definition": result}


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("verify", "controls", "retire", "options", "configure", "enable"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
