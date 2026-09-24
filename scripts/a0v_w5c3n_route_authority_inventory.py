#!/usr/bin/env python3
"""Read-only metadata inventory for predecessor-free route planning."""

from __future__ import annotations

import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3m_natural_enable as prior
import a0v_w5c3b_successor_lifecycle as live


def inventory():
    audit = prior.audit()
    group = live.successor.GROUP
    installation = audit["installationId"]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        routes = [dict(row) for row in conn.execute("""SELECT operation_id, handler_kind,
          installation_id::text, generation::text, execution_epoch, operation_fence,
          revision, cutover_group_id::text, cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (group,)).fetchall()]
        first = [dict(row) for row in conn.execute("""SELECT receipt_id::text,
          installation_id::text, generation::text, group_id::text, content_hash
          FROM extension_dispatch_registration_receipt WHERE org_id='org-org'
          AND project_id='dev-project' AND group_id=%s ORDER BY created_at""",
          (group,)).fetchall()]
        successor = [dict(row) for row in conn.execute("""SELECT receipt_id::text,
          installation_id::text, generation::text, group_id::text, content_hash
          FROM extension_dispatch_successor_registration_receipt WHERE org_id='org-org'
          AND project_id='dev-project' AND group_id=%s ORDER BY created_at""",
          (group,)).fetchall()]
        cutover = [dict(row) for row in conn.execute("""SELECT cutover_operation_id::text,
          kind, status, target_installation_id::text, target_generation::text,
          expected_group_revision, target_group_revision
          FROM extension_dispatch_cutover_operation WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY created_at DESC LIMIT 5""", (group,)).fetchall()]
        detach = [dict(row) for row in conn.execute("""SELECT receipt_id::text,
          phase, content_hash, runtime_operation_id::text
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org'
          AND project_id='dev-project' AND phase='detach'
          ORDER BY created_at DESC LIMIT 5""").fetchall()]
        current_detach = conn.execute("""SELECT r.receipt_id::text,r.content_hash,
          r.authority_data->>'status' AS status,
          r.authority_data->'dispatchSnapshot' AS dispatch_snapshot,
          l.status AS lifecycle_status,l.fenced_group_revision,
          l.activation_operation_id::text,
          o.status AS disable_status,o.phase AS disable_phase,
          b.enabled,b.operation_fence,b.desired_state,b.observed_state,
          (SELECT i.active_revision FROM bundle_installation i
           WHERE i.org_id=a.org_id AND i.project_id=a.project_id
           AND i.installation_id=a.target_installation_id) AS old_active_revision,
          (SELECT count(*) FROM extension_runtime_resource_lease lease
           WHERE lease.org_id='org-org' AND lease.project_id='dev-project'
           AND lease.generation=b.generation AND
           (lease.cleanup_state<>'released' OR NOT lease.observed_release)) AS unsafe_resources
          FROM extension_dispatch_lifecycle_receipt r
          JOIN extension_dispatch_lifecycle_operation l
            USING(org_id,project_id,runtime_operation_id)
          JOIN extension_runtime_operation o
            ON o.org_id=r.org_id AND o.project_id=r.project_id
            AND o.operation_id=r.runtime_operation_id
          JOIN extension_dispatch_cutover_operation a
            ON a.org_id=l.org_id AND a.project_id=l.project_id
            AND a.cutover_operation_id=l.activation_operation_id
          JOIN extension_runtime_binding b
            ON b.org_id=a.org_id AND b.project_id=a.project_id
            AND b.installation_id=a.target_installation_id
            AND b.generation=a.target_generation
          WHERE r.org_id='org-org' AND r.project_id='dev-project'
          AND r.receipt_id=%s AND r.phase='detach'""",
          ("d64e1b84-bdf9-4d15-b740-16673fcd651a",)).fetchone()
        selection = [dict(row) for row in conn.execute("""SELECT installation_id::text,
          generation::text, count(*) AS revisions, count(DISTINCT pipeline_id) AS pipelines,
          max(created_at)::text AS latest_created_at
          FROM pipeline_source_selection_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s
          GROUP BY installation_id,generation""", (installation,)).fetchall()]
        controls = conn.execute("""SELECT count(*) AS revisions,
          count(DISTINCT pipeline_id) AS pipelines
          FROM pipeline_runtime_control_revision WHERE org_id='org-org'
          AND project_id='dev-project' AND installation_id=%s""",
          (installation,)).fetchone()
        definitions = [dict(row) for row in conn.execute("""SELECT definition_id::text,
          revision,state,installation_id::text,generation::text
          FROM pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' ORDER BY definition_id""").fetchall()]
        schedules = dict(conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE enabled) AS enabled FROM meta_schedule
          WHERE org_id='org-org' AND project_id='dev-project' AND pipeline_id IN
          (SELECT pipeline_id FROM pipeline_source_selection_revision
          WHERE org_id='org-org' AND project_id='dev-project'
          AND installation_id=%s)""", ("c6812824-a0c3-4adc-9ebc-d56178ae135c",)).fetchone())
        columns = [dict(row) for row in conn.execute("""SELECT table_name,column_name
          FROM information_schema.columns WHERE table_schema='public'
          AND table_name=ANY(%s) ORDER BY table_name,ordinal_position""",
          (["pipeline_runtime_control_revision", "pipeline_schedule_control_binding",
            "pipeline_snapshot_schedule_definition_head"],)).fetchall()]
        definition = conn.execute("""SELECT pg_get_functiondef(
          'public.extension_dispatch_successor_register_a0v_056(jsonb,text)'::regprocedure)
          AS body""").fetchone()["body"]
    if len(routes) != 9 or any(row["handler_kind"] != "legacy" or
            row["operation_fence"] is not True for row in routes):
        raise ValueError("W5C3N_ROUTE_GATE_DRIFT")
    return {"prior": audit, "routes": routes, "firstReceipts": first,
            "successorReceiptCount": len(successor),
            "latestSuccessorReceipt": successor[-1] if successor else None,
            "newInstallationSuccessorReceipts": [row for row in successor
              if row["installation_id"] == installation],
            "recentCutovers": cutover,
            "recentDetachReceipts": detach, "newInstallationSelections": selection,
            "currentDetachAuthority": dict(current_detach) if current_detach else None,
            "newInstallationControls": dict(controls),
            "definitionHeads": definitions, "oldSchedules": schedules,
            "uninstalledSuccessorGuardLoaded": all(token in definition for token in
              ("v_old_binding.desired_state='uninstalled'",
               "v_old_binding.observed_state='stopped'",
               "i.active_revision IS NULL AND r.state='uninstalled'")),
            "metadataColumns": columns}


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, default=str))
