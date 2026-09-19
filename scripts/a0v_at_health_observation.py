#!/usr/bin/env python3
"""Read-only AT lease observation; never invokes runtime or business operations."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import a0v_at_replacement_recovery as replacement
from a0v_formal_text_model_renewal import database_connect


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-at"
OPERATION = "e573dbe9-e696-44e0-b851-b5f31d9a8937"
TARGET_DELTA = 12


def snapshot() -> dict:
    profile = replacement.load_profile()
    installation = profile.observe_installation(replacement.load_profile()._initial("at")["installationId"])
    binding = installation["bindings"]
    if (str(installation["head"]["installation_id"]) != "631e6d01-a5bb-4865-95eb-07d5665ed957"
            or len(binding) != 1 or str(binding[0]["generation"]) != "63ea2c87-f185-4b02-b792-1e3073db4a1b"
            or (binding[0]["revision"], binding[0]["execution_epoch"]) != (6, 3)
            or binding[0]["enabled"] is not True or binding[0]["operation_fence"] is not False
            or binding[0]["desired_state"] != "enabled" or binding[0]["observed_state"] != "ready"):
        raise RuntimeError("exact live AT binding required")
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
            AND installation_id=%s AND generation=%s AND execution_epoch=3 AND revision=111
            AND cutover_group_revision=138 AND operation_fence=false) routes,
          (SELECT count(*) FROM bundle_installation WHERE org_id='dev-org'
            AND project_id='dev-project') canary""", (OPERATION, OPERATION, OPERATION,
            "631e6d01-a5bb-4865-95eb-07d5665ed957", replacement.GROUP,
            "631e6d01-a5bb-4865-95eb-07d5665ed957",
            "63ea2c87-f185-4b02-b792-1e3073db4a1b")).fetchone())
        resources = [dict(row) for row in conn.execute("""SELECT resource_id::text,cleanup_state,
          observed_release,expires_at FROM extension_runtime_resource_lease
          WHERE operation_id=%s ORDER BY resource_id""", (OPERATION,)).fetchall()]
    if (facts["attempts"] or facts["running"] or facts["unresolved"] or facts["runtime_pending"]
            or facts["routes"] != 9 or facts["canary"] != 0 or len(resources) != 3
            or any(row["cleanup_state"] != "pending" or row["observed_release"] is not False
                   or row["expires_at"] <= facts["observed_at"] for row in resources)):
        raise RuntimeError("AT health observation boundary drifted")
    return {"facts": facts, "resources": resources, "binding": binding[0]}


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
            return {"outcome": "AT_HEALTH_OBSERVATION_GREEN", "baseline": baseline,
                "targetDelta": TARGET_DELTA, "final": current,
                "startedAt": started, "finishedAt": datetime.now(timezone.utc),
                "samples": len(observations)}
        if (datetime.now(timezone.utc) - started).total_seconds() >= timeout_seconds:
            raise TimeoutError("AT did not reach the required renewal delta")
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
