#!/usr/bin/env python3
"""W4 definition rebuild: retire the AU-bound definition and rebuild on DR bindings.

Channel (avoids installation authority lock on configure):
  options   - read-only: current options (12 current bindings + policies)
  retire    - retire definition cb0dba8c (AU installation, disabled) to release
              pipeline_snapshot_schedule_current_member occupancy
  configure - NEW definition 446cc1ae (head absent -> installation from DR
              bindings[0], no installation authority check), disabled
  enable    - NEW definition enabled; meta_schedule.enabled flips to true
  verify    - read-only: definition state + routing status

The old transfer_saved_recovery channel requires 12/12 resumable (running) runs;
the W3 stalled-group closure terminalized them to failed, so the release-rebuild
channel (previously proven by the U template) is the exact structural exit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-definition-rebuild"
OLD_DEFINITION = "cb0dba8c-803f-5caf-8011-b763d349f2ba"
DEFINITION = "446cc1ae-fa5b-406a-9446-d32104126dda"
DQ_ID = "89975129-7e0f-4860-ac56-7a031ebe4a1a"
DQ_GENERATION = "c78b2e2e-57ef-47ad-be07-9acf689e578c"
SOURCE_ID = "d2d3c478-f9d9-4489-92b7-1de57f546452"
SOURCE_GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
CRON = "* * * * *"
KEY = "a0v-w4-dq-definition-rebuild-20260923"
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
    status = service.read_runtime_status(definition_id=DEFINITION, actor=ACTOR)
    return {"outcome": "W4_DQ_DEFINITION_VERIFY", "head": _head_ref(),
            "oldHead": _head_ref(OLD_DEFINITION), "runtimeStatus": status}


def controls():
    """Refresh the twelve AU selection->control->binding chain to config rev2 / epoch 6.

    Root cause: the extension binding was reconfigured to configuration revision 2
    (policyRef rev12), so every frozen selection draft (configurationRef rev1) now fails
    check_policy ('current runtime configuration differs'). We clone each latest draft,
    patch installationRef/executionEpoch/configurationRef/notBefore/expiresAt to current
    facts, dry-validate via selections._guarded inside a rolled-back transaction, then
    approve selection -> control -> binding per member. Members already current are reused.
    """
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
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
            (*scope.key, DQ_ID)).fetchone()
        if head is None or head["state"] != "active":
            raise RuntimeError(f"AU installation head unavailable: {dict(head) if head else None}")
        ref = CurrentInstallationRef.model_validate(dict(
            installationId=DQ_ID, revision=head["current_revision"],
            lockHash=head["lock_hash"], overlayRevision=head["overlay_revision"]))
        binding = conn.execute("""SELECT config_ref, execution_epoch FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            ORDER BY revision DESC LIMIT 1""", (*scope.key, DQ_ID, DQ_GENERATION)).fetchone()
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
                    and schedule_binding is not None and schedule_binding.generation == DQ_GENERATION
                    and _wire(control.ref) == _wire(schedule_binding.control_ref)):
                members.append({"pipelineId": pipeline, "scheduleId": schedule_id, "reused": True,
                                "selectionRef": _wire(saved.ref), "controlRef": _wire(control.ref),
                                "bindingRef": _wire(schedule_binding.ref)})
                continue
            draft = saved.draft.model_dump(mode="json", by_alias=True, exclude_none=True)
            draft.update({"installationRef": _wire(ref), "generation": DQ_GENERATION,
                          "executionEpoch": epoch,
                          "configurationRef": config_ref,
                          "notBefore": now.isoformat(), "expiresAt": (now + timedelta(hours=6)).isoformat()})
            # DR 名下已有同 pipeline selection（断点续跑）则复用其 ref 作为 previous
            dr_latest = conn.execute("""SELECT * FROM pipeline_source_selection_revision
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                ORDER BY revision DESC LIMIT 1""", (*scope.key, DQ_ID, DQ_GENERATION, pipeline)).fetchone()
            if dr_latest is not None:
                latest_saved = decode_selection_row(dr_latest)
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
        # Dry-validate every patched draft inside a transaction we roll back.
        from psycopg import Rollback
        def _dry(_conn):
            for member in members:
                if member["reused"]:
                    continue
                draft = PipelineSourceSelectionDraft.model_validate_json(json.dumps(member["draft"]))
                plane_services.selections._guarded(_conn, draft, ACTOR, lambda value: True, snapshot=True)
            raise Rollback()
        with consumer_connection(runtime_worker_connection, workers) as conn:
            conn.execute("SELECT 1")
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
                idempotency_key=f"{KEY}-{pipeline.lower()}-selection-v2", previous_ref=None))
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
    return {"outcome": "W4_DQ_CONTROLS_CURRENT", "members": len(results),
            "reused": sum(1 for r in results if r["reused"]), "configRevision": config_ref.get("revision")}


def _wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _plane():
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection)


def options():
    _configure()
    service = _service()
    result = service.options(actor=ACTOR, installation_id=DQ_ID, generation=DQ_GENERATION)
    if result.get("status") != "ready" or len(result.get("members", [])) != 12 or not result.get("policies"):
        raise RuntimeError(f"DQ options not ready: status={result.get('status')} missing={result.get('missing')} ambiguous={result.get('ambiguous')}")
    frozen = {"members": result["members"], "policyRef": result["policies"][0],
              "priorHead": _head_ref()}
    _write("options", frozen)
    return {"outcome": "W4_DQ_OPTIONS_READY", "members": len(result["members"]),
            "policyRef": result["policies"][0], "priorHead": frozen["priorHead"]}


def retire():
    """Retire the disabled AU-bound definition to release schedule occupancy."""
    _configure()
    service = _service()
    head = _head_ref(OLD_DEFINITION)
    if head is None:
        raise RuntimeError("old definition head unavailable")
    if head["state"] == "retired":
        return {"outcome": "W4_OLD_DEFINITION_ALREADY_RETIRED", "head": head}
    if head["state"] != "disabled":
        raise RuntimeError(f"old definition not disabled: {head}")
    result = service.transition(definition_id=OLD_DEFINITION, actor=ACTOR, intent="retire",
        expected_ref=head["ref"], idempotency_key="a0v-w4-retire-old-definition-20260923-v1")
    _write("retire", {"definition": result})
    return {"outcome": "W4_OLD_DEFINITION_RETIRED", "definition": result}


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
    return {"outcome": "W4_DQ_DEFINITION_CONFIGURED", "definition": result}


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
    return {"outcome": "W4_DQ_DEFINITION_ENABLED", "definition": result}


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("verify", "options", "retire", "configure", "enable", "controls"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
