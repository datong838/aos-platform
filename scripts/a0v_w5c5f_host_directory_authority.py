#!/usr/bin/env python3
"""Read-only exact host-directory gate; never proves all-machine quietness."""

from __future__ import annotations

import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4t_closure_feasibility as boundary


HOST_ID = "a0v-local-ecommerce-host-20260912"
DIRECTORY_ROLE = "aos_a0v_directory_20260912"
GENERATION = boundary.prior.prior.prepared.registered.GENERATION


def _frozen(reason):
    return {"outcome": "FROZEN_HOST_DIRECTORY_AUTHORITY", "reason": reason,
            "automaticAction": False, "topologyComplete": False,
            "closureAuthorized": False}


def classify(value):
    """A clean managed directory remains insufficient to authorize closure."""
    try:
        assignment = {"host_id": HOST_ID, "state": "assigned", "revision": 1}
        identity = {"database_role": DIRECTORY_ROLE, "host_id": HOST_ID,
                    "enabled": True, "revision": 1, "role_oid_matches": True,
                    "eligible_directory_member": True, "non_privileged_login": True}
        if (value["assignment"] != assignment
                or value["assignmentHistory"] != [assignment]
                or value["identities"] != [identity]
                or value["identityHistory"] != [{key: identity[key] for key in
                    ("database_role", "host_id", "enabled", "revision", "role_oid_matches")}]
                or value["leaseStates"] != [
                    {"cleanup_state": "released", "observed_release": True, "n": 3}]
                or value["definition"] != {"revision": 4, "state": "disabled",
                                           "content_hash": boundary.HASH}
                or value["runs"] != {"n": 12, "running": 12}
                or value["closureReceipts"] != 0):
            return _frozen("DIRECTORY_LEASE_OR_ORIGINAL_GROUP_DRIFT")
        return {"outcome": "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY",
                "automaticAction": False, "topologyComplete": False,
                "closureAuthorized": False, "assignedHostId": HOST_ID,
                "releasedResourceLeases": 3, "runningOriginalRuns": 12}
    except (KeyError, TypeError, ValueError):
        return _frozen("INCOMPLETE_DIRECTORY_SNAPSHOT")


def observe():
    """A single repeatable-read, read-only database snapshot; counts only."""
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        assignment = conn.execute("""SELECT host_id,state,revision FROM
            extension_runtime_host_assignment WHERE org_id='org-org'
            AND project_id='dev-project'""").fetchone()
        assignment_history = [dict(row) for row in conn.execute("""SELECT host_id,state,revision
            FROM extension_runtime_host_assignment_revision WHERE org_id='org-org'
            AND project_id='dev-project' ORDER BY revision""").fetchall()]
        identities = [dict(row) for row in conn.execute("""SELECT
            i.database_role::text,i.host_id,i.enabled,i.revision,
            (i.database_role_oid=r.oid) AS role_oid_matches,
            (r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls) AS non_privileged_login,
            pg_has_role(i.database_role::text,'aos_extension_directory','member')
                AS eligible_directory_member
            FROM extension_runtime_host_identity i
            LEFT JOIN pg_roles r ON r.rolname=i.database_role::text
            ORDER BY i.host_id""").fetchall()]
        history = [dict(row) for row in conn.execute("""SELECT
            h.database_role::text,h.host_id,h.enabled,h.revision,
            (h.database_role_oid=r.oid) AS role_oid_matches
            FROM extension_runtime_host_identity_revision h
            LEFT JOIN pg_roles r ON r.rolname=h.database_role::text
            ORDER BY h.database_role,h.revision""").fetchall()]
        leases = [dict(row) for row in conn.execute("""SELECT cleanup_state,
            observed_release,count(*) AS n FROM extension_runtime_resource_lease
            WHERE org_id='org-org' AND project_id='dev-project' AND generation=%s
            GROUP BY cleanup_state,observed_release ORDER BY cleanup_state,observed_release""",
            (GENERATION,)).fetchall()]
        definition = conn.execute("""SELECT revision,state,content_hash FROM
            pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
            AND project_id='dev-project' AND definition_id=%s""",
            (boundary.DEFINITION,)).fetchone()
        runs = dict(conn.execute("""SELECT count(*) AS n,
            count(*) FILTER(WHERE r.status='running' AND r.finished_at IS NULL
                AND r.executor_id='' AND NOT r.executor_stopped AND r.rows_written=0
                AND r.error_code='' AND r.error_message='' AND NOT s.enabled) AS running
            FROM pipeline_snapshot_schedule_member m JOIN meta_schedule_run r
              ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
            JOIN meta_schedule s ON (s.org_id,s.project_id,s.id)=
              (m.org_id,m.project_id,m.schedule_id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s""",
            (boundary.GROUP,)).fetchone())
        receipts = conn.execute("""SELECT count(*) AS n FROM
            pipeline_snapshot_stalled_group_closure_receipt WHERE org_id='org-org'
            AND project_id='dev-project' AND group_id=%s""",
            (boundary.GROUP,)).fetchone()["n"]
    return {"assignment": dict(assignment) if assignment else None,
            "assignmentHistory": assignment_history, "identities": identities,
            "identityHistory": history, "leaseStates": leases,
            "definition": dict(definition) if definition else None,
            "runs": runs, "closureReceipts": receipts}


if __name__ == "__main__":
    try:
        result = classify(observe())
    except Exception as error:
        result = _frozen("OBSERVATION_" + type(error).__name__)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] == "FROZEN_HOST_DIRECTORY_AUTHORITY" else 0)
