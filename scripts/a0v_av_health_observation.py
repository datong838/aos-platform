#!/usr/bin/env python3
"""Read-only AV lease observation; never invokes runtime or business operations."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import a0v_av_replacement_recovery as replacement
from a0v_formal_text_model_renewal import database_connect


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-av"
OPERATION = "54c1cba8-3ddd-4f74-a222-9c26a2b99627"
TARGET_DELTA = 12
DEFINITION = "cb0dba8c-803f-5caf-8011-b763d349f2ba"
SNAPSHOT_GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
LINK_KEY = ("snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:"
            "bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b")


def snapshot() -> dict:
    profile = replacement.load_profile()
    installation = profile.observe_installation(replacement.load_profile()._initial("av")["installationId"])
    binding = installation["bindings"]
    if (str(installation["head"]["installation_id"]) != "5f01eda8-ca5f-4892-8510-385704ccddb2"
            or len(binding) != 1 or str(binding[0]["generation"]) != "17104053-f4c9-47e1-89b0-f3f353076dda"
            or (binding[0]["revision"], binding[0]["execution_epoch"]) != (6, 3)
            or binding[0]["enabled"] is not True or binding[0]["operation_fence"] is not False
            or binding[0]["desired_state"] != "enabled" or binding[0]["observed_state"] != "ready"):
        raise RuntimeError("exact live AV binding required")
    with database_connect("aos_meta_head")() as conn:
        facts = dict(conn.execute("""SELECT clock_timestamp() observed_at,
          (SELECT count(*) FROM extension_runtime_event WHERE operation_id=%s
            AND type='runtime_lease_renewed') renewals,
          (SELECT max(sequence) FROM extension_runtime_event WHERE operation_id=%s
            AND type='runtime_lease_renewed') last_sequence,
          (SELECT max(occurred_at) FROM extension_runtime_event WHERE operation_id=%s
            AND type='runtime_lease_renewed') last_renewed_at,
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s) attempts,
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM extension_runtime_operation WHERE org_id='org-org'
            AND project_id='dev-project' AND status NOT IN ('succeeded','failed','cancelled')) runtime_pending,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='org-org'
            AND project_id='dev-project' AND cutover_group_id=%s AND handler_kind='extension'
            AND installation_id=%s AND generation=%s AND execution_epoch=3 AND revision=117
            AND cutover_group_revision=144 AND operation_fence=false) routes,
          (SELECT count(*) FROM bundle_installation WHERE org_id='dev-org'
            AND project_id='dev-project') canary""", (OPERATION, OPERATION, OPERATION,
            "5f01eda8-ca5f-4892-8510-385704ccddb2", replacement.GROUP,
            "5f01eda8-ca5f-4892-8510-385704ccddb2",
            "17104053-f4c9-47e1-89b0-f3f353076dda")).fetchone())
        resources = [dict(row) for row in conn.execute("""SELECT resource_id::text,cleanup_state,
          observed_release,expires_at FROM extension_runtime_resource_lease
          WHERE operation_id=%s ORDER BY resource_id""", (OPERATION,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          (DEFINITION,)).fetchone()
        boundary = dict(conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_member
            WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s) members,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s
              AND r.status='running' AND r.executor_stopped IS FALSE AND r.finished_at IS NULL) saved_runs,
          (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s) dataset_receipts,
          (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id='org-org'
            AND workspace_id='dev-project' AND idempotency_key=%s) store_receipts,
          (SELECT count(*) FROM ecom_link WHERE org_id='org-org' AND workspace_id='dev-project') store_links,
          (SELECT count(*) FROM projection_outbox WHERE org_id='org-org' AND workspace_id='dev-project'
            AND projected IS FALSE) projection_pending""",
          (SNAPSHOT_GROUP, SNAPSHOT_GROUP, SNAPSHOT_GROUP, LINK_KEY)).fetchone())
    if (facts["attempts"] or facts["running"] or facts["unresolved"] or facts["runtime_pending"]
            or facts["routes"] != 9 or facts["canary"] != 0 or len(resources) != 3
            or definition is None or dict(definition) != {"revision": 73, "state": "disabled"}
            or boundary != {"members": 12, "saved_runs": 12, "dataset_receipts": 12,
                            "store_receipts": 0, "store_links": 0, "projection_pending": 0}
            or any(row["cleanup_state"] != "pending" or row["observed_release"] is not False
                   or row["expires_at"] <= facts["observed_at"] for row in resources)):
        raise RuntimeError("AV health observation boundary drifted")
    return {"facts": facts, "resources": resources, "binding": binding[0],
            "definition": dict(definition), "boundary": boundary}


def watch(baseline: int, *, poll_seconds: int, timeout_seconds: int) -> dict:
    started = datetime.now(timezone.utc)
    observations = []
    while True:
        current = snapshot()
        observations.append(current)
        delta = current["facts"]["renewals"] - baseline
        print(json.dumps({"observedAt": current["facts"]["observed_at"],
            "renewals": current["facts"]["renewals"], "delta": delta}, default=str), flush=True)
        if delta >= TARGET_DELTA:
            return {"outcome": "AV_HEALTH_OBSERVATION_GREEN", "baseline": baseline,
                "targetDelta": TARGET_DELTA, "final": current,
                "startedAt": started, "finishedAt": datetime.now(timezone.utc),
                "samples": len(observations)}
        if (datetime.now(timezone.utc) - started).total_seconds() >= timeout_seconds:
            raise TimeoutError("AV did not reach the required renewal delta")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=int, required=True)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=960)
    args = parser.parse_args()
    result = watch(args.baseline, poll_seconds=args.poll_seconds, timeout_seconds=args.timeout_seconds)
    output = STATE / "health-observation-result.json"
    replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
