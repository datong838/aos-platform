#!/usr/bin/env python3
"""Read-only feasibility gate for retiring the disabled DR definition."""

from __future__ import annotations

import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c3y_job_authority_inventory as jobs
import a0v_w5c3t_cutover_prepare as prepared

DEFINITION = "446cc1ae-fa5b-406a-9446-d32104126dda"
ACTOR = prepared.ACTOR


def inventory():
    cutover = resumed.audit()
    current = jobs.inventory()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        head = dict(conn.execute("""SELECT h.definition_id::text,h.revision,h.content_hash,
          h.state,h.installation_id::text,h.generation::text,i.etag_version,
          r.state AS installation_state
          FROM pipeline_snapshot_schedule_definition_head h
          JOIN bundle_installation i ON i.org_id=h.org_id AND i.project_id=h.project_id
            AND i.installation_id=h.installation_id
          JOIN bundle_installation_revision r ON r.org_id=i.org_id
            AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk
            AND r.revision=i.current_revision
          WHERE h.org_id='org-org' AND h.project_id='dev-project'
            AND h.definition_id=%s""", (DEFINITION,)).fetchone())
        membership = conn.execute("""SELECT role FROM meta_membership
          WHERE org_id='org-org' AND project_id='dev-project' AND subject=%s""",
          (ACTOR,)).fetchone()
        runs = dict(conn.execute("""SELECT count(*) AS total,
          count(*) FILTER (WHERE status='running') AS running,
          count(*) FILTER (WHERE executor_stopped IS NOT TRUE) AS not_stopped,
          count(*) FILTER (WHERE status='running' OR executor_stopped IS NOT TRUE) AS retirement_blocking
          FROM meta_schedule_run WHERE org_id='org-org' AND project_id='dev-project'
          AND schedule_id=ANY(%s)""",
          ([row["schedule_id"] for row in current["oldSlots"]],)).fetchone())
        claims = dict(conn.execute("""SELECT count(*) AS groups,
          count(*) FILTER (WHERE EXISTS (
            SELECT 1 FROM pipeline_snapshot_schedule_member m
            JOIN meta_schedule_run run ON run.org_id=m.org_id AND run.project_id=m.project_id
              AND run.id=m.run_id
            WHERE m.org_id=c.org_id AND m.project_id=c.project_id
              AND m.group_id=c.group_id AND
              (run.status='running' OR run.executor_stopped IS NOT TRUE))) AS unfinished_groups
          FROM pipeline_snapshot_schedule_claim c WHERE c.org_id='org-org'
          AND c.project_id='dev-project'
          AND c.request->'definitionRef'->>'resourceId'=%s""",
          ("snapshot-schedule-" + DEFINITION,)).fetchone())
        resources = dict(conn.execute("""SELECT count(*) AS total,
          count(*) FILTER (WHERE cleanup_state='released' AND observed_release) AS released
          FROM extension_runtime_resource_lease WHERE org_id='org-org'
          AND project_id='dev-project' AND generation=%s""", (head["generation"],)).fetchone())
    if (cutover["outcome"] != "W5C3X_RESUME_GREEN"
            or current["outcome"] != "W5C3Y_JOB_AUTHORITY_INVENTORY_GREEN"
            or head["revision"] != 3 or head["state"] != "disabled"
            or len(current["currentMembers"]) != 12):
        raise ValueError("W5C3Z_RETIREMENT_INVENTORY_DRIFT")
    return {"outcome": "W5C3Z_RETIREMENT_FEASIBILITY_READ",
            "head": head, "actorRole": membership["role"] if membership else None,
            "runs": runs, "claims": claims, "resources": resources,
            "schedulesEnabled": 0, "currentMembers": 12,
            "releasedRetirementAllowed": (head["installation_state"] == "uninstalled"
                and membership is not None and membership["role"] == "admin"),
            "retirementExecutionClear": runs["retirement_blocking"] == 0}


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, default=str))
