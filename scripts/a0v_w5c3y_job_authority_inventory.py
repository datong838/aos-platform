#!/usr/bin/env python3
"""Read only control metadata after third-successor cutover; never read source payloads."""

from __future__ import annotations

import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3x_cutover_resume as resumed
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled


def inventory():
    cutover = resumed.audit()
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        selection = [dict(row) for row in conn.execute("""SELECT installation_id::text,
          generation::text,pipeline_id,selection_id::text,revision,created_at
          FROM pipeline_source_selection_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s
          ORDER BY pipeline_id,revision""", (prepared.registered.INSTALLATION,)).fetchall()]
        controls = [dict(row) for row in conn.execute("""SELECT installation_id::text,
          generation::text,pipeline_id,control_id::text,revision,created_at
          FROM pipeline_runtime_control_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s
          ORDER BY pipeline_id,revision""", (prepared.registered.INSTALLATION,)).fetchall()]
        old_slots = [dict(row) for row in conn.execute("""SELECT s.id AS schedule_id,
          s.pipeline_id,s.enabled,b.binding_id::text,b.revision AS binding_revision,
          b.installation_id::text AS binding_installation,
          b.generation::text AS binding_generation
          FROM meta_schedule s LEFT JOIN LATERAL (
            SELECT binding_id,revision,installation_id,generation
            FROM pipeline_schedule_control_binding b
            WHERE b.org_id=s.org_id AND b.project_id=s.project_id
              AND b.schedule_id=s.id ORDER BY revision DESC LIMIT 1
          ) b ON true
          WHERE s.org_id='org-org' AND s.project_id='dev-project'
          AND s.pipeline_id IN (SELECT DISTINCT pipeline_id
            FROM pipeline_source_selection_revision WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s)
          ORDER BY s.id""", ("c6812824-a0c3-4adc-9ebc-d56178ae135c",)).fetchall()]
        definitions = [dict(row) for row in conn.execute("""SELECT definition_id::text,
          revision,state,installation_id::text,generation::text
          FROM pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' ORDER BY definition_id""").fetchall()]
        current_members = [dict(row) for row in conn.execute("""SELECT schedule_id,
          definition_id::text,revision FROM pipeline_snapshot_schedule_current_member
          WHERE org_id='org-org' AND project_id='dev-project'
          ORDER BY schedule_id""").fetchall()]
        old_selection = [dict(row) for row in conn.execute("""SELECT pipeline_id,
          count(*) AS revisions,max(created_at)::text AS last_created_at
          FROM pipeline_source_selection_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s
          GROUP BY pipeline_id ORDER BY pipeline_id""",
          ("c6812824-a0c3-4adc-9ebc-d56178ae135c",)).fetchall()]
        attempts = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND state='running') AS running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved""").fetchone())
    if (cutover["outcome"] != "W5C3X_RESUME_GREEN"
            or selection or controls or len(old_slots) != 12
            or any(item["enabled"] for item in old_slots)
            or attempts != {"running": 0, "unresolved": 0}
            or runtime["counts"]["canary"] != 0):
        raise ValueError("W5C3Y_JOB_INVENTORY_GATE_DRIFT")
    return {"outcome": "W5C3Y_JOB_AUTHORITY_INVENTORY_GREEN",
            "cutover": cutover, "newSelections": selection,
            "newControls": controls, "oldSlots": old_slots,
            "oldSelectionSummary": old_selection,
            "definitions": definitions, "currentMembers": current_members,
            "attempts": attempts}


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, default=str))
