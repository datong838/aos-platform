#!/usr/bin/env python3
"""Dry-check twelve current successor control drafts without source reads or writes."""

from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path

from psycopg import Rollback

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c4a_dr_definition_retire as retired
import a0v_w5c3t_cutover_prepare as prepared

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4c-controls-preflight")
DS_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"
DS_GENERATION = "b59582cc-2abf-472d-8f59-bfc8be1138c8"


def _wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def preflight():
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.ec_ingress_journal import _digest
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C4C_PREFLIGHT_EXISTS_RECONCILE_FIRST")
    if (resumed.audit()["outcome"] != "W5C3X_RESUME_GREEN"
            or retired.audit()["outcome"] != "W5C4A_DR_DEFINITION_RETIRED_GREEN"):
        raise ValueError("W5C4C_RUNTIME_OR_DEFINITION_DRIFT")
    scope = TenantScope("org-org", "dev-project")
    plane = prepared._plane()
    services = plane.pipeline_control_factory.build(scope)
    materials = []
    with consumer_connection(runtime_worker_connection,
                             {"org_id": scope.org_id, "project_id": scope.project_id}) as conn:
        head = conn.execute("""SELECT i.current_revision,r.state,r.lock_hash,r.overlay_revision
          FROM bundle_installation i JOIN bundle_installation_revision r
          ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=
             (r.org_id,r.project_id,r.installation_pk,r.revision)
          WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
          (*scope.key, prepared.registered.INSTALLATION)).fetchone()
        binding = conn.execute("""SELECT config_ref,execution_epoch,revision,enabled,
          operation_fence FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
          AND installation_id=%s AND generation=%s""",
          (*scope.key, prepared.registered.INSTALLATION,
           prepared.registered.GENERATION)).fetchone()
        if (head is None or head["state"] != "active" or binding is None
                or binding["revision"] != 6 or binding["execution_epoch"] != 3
                or binding["enabled"] is not True or binding["operation_fence"] is not False):
            raise ValueError("W5C4C_CURRENT_INSTALLATION_DRIFT")
        installation_ref = CurrentInstallationRef.model_validate({
            "installationId": prepared.registered.INSTALLATION,
            "revision": head["current_revision"], "lockHash": head["lock_hash"],
            "overlayRevision": head["overlay_revision"]})
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        rows = conn.execute("""SELECT DISTINCT pipeline_id
          FROM pipeline_source_selection_revision WHERE org_id=%s AND project_id=%s
          AND installation_id=%s AND generation=%s ORDER BY pipeline_id""",
          (*scope.key, DS_ID, DS_GENERATION)).fetchall()
        if len(rows) != 12:
            raise ValueError("W5C4C_TWELVE_PREDECESSOR_PIPELINES_REQUIRED")
        for row in rows:
            pipeline = row["pipeline_id"]
            prior = conn.execute("""SELECT * FROM pipeline_source_selection_revision
              WHERE org_id=%s AND project_id=%s AND installation_id=%s
              AND generation=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1""",
              (*scope.key, DS_ID, DS_GENERATION, pipeline)).fetchone()
            schedule = conn.execute("""SELECT id,enabled FROM meta_schedule
              WHERE org_id=%s AND project_id=%s AND pipeline_id=%s""",
              (*scope.key, pipeline)).fetchall()
            graph = conn.execute("""SELECT revision,payload FROM phase5_pipeline_graph
              WHERE org_id=%s AND project_id=%s AND pipeline_id=%s""",
              (*scope.key, pipeline)).fetchone()
            if (prior is None or len(schedule) != 1 or schedule[0]["enabled"] is not False
                    or graph is None):
                raise ValueError("W5C4C_MEMBER_METADATA_DRIFT")
            saved = decode_selection_row(prior)
            draft = saved.draft.model_dump(mode="json", by_alias=True, exclude_none=True)
            if (graph["revision"] != draft["graphRevision"]
                    or _digest(graph["payload"]) != draft["graphHash"]):
                raise ValueError("W5C4C_GRAPH_DRIFT")
            source = SourceConfigurationRevisionStore(HostTransaction(conn), scope).read_current(
                draft["sourceId"])
            if source is None or _wire(source.ref) != draft["sourceConfigurationRef"]:
                raise ValueError("W5C4C_SOURCE_CONFIG_DRIFT")
            draft.update({"installationRef": _wire(installation_ref),
                          "generation": prepared.registered.GENERATION,
                          "executionEpoch": 3, "configurationRef": binding["config_ref"],
                          "notBefore": now.isoformat(),
                          "expiresAt": (now + timedelta(hours=12)).isoformat()})
            candidate = PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft))
            materials.append({"pipelineId": pipeline, "scheduleId": schedule[0]["id"],
                              "draft": _wire(candidate), "oldSelectionRef": _wire(saved.ref)})
        checked = []
        try:
            with conn.transaction():
                for material in materials:
                    candidate = PipelineSourceSelectionDraft.model_validate_json(
                        json.dumps(material["draft"]))
                    services.selections._guarded(conn, candidate, prepared.ACTOR,
                                                 lambda _compiled: True, snapshot=True)
                    checked.append(material["pipelineId"])
                raise Rollback()
        except Rollback:
            pass
    if len(checked) != 12:
        raise ValueError("W5C4C_DRY_CHECK_INCOMPLETE")
    _write("material", {"installationId": prepared.registered.INSTALLATION,
                        "generation": prepared.registered.GENERATION,
                        "executionEpoch": 3, "configRef": binding["config_ref"],
                        "checkedAt": now.isoformat(), "members": materials})
    return {"outcome": "W5C4C_TWELVE_CONTROL_DRAFTS_GREEN",
            "members": len(materials), "dryChecked": len(checked),
            "executionAuthorized": False, "sourceRowsRead": 0,
            "databaseWrites": 0, "scheduleEnabled": 0}


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False, default=str))
