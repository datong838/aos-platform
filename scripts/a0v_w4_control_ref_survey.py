#!/usr/bin/env python3
"""W4 read-only survey: governance refs frozen in the 12 latest runtime controls."""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.update({
    "AOS_DOTENV_DISABLED": "1",
    "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(
        ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bm-runtime-credentials/runtime-host-identities.json"),
    "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
    "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
    "AOS_BUNDLE_ROOT": str(
        ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bn-canonical-alias-registry/signed-bundles"),
})
sys.path.insert(0, "services/aos-api")

from aos_api.extension_runtime.consumer_connection import consumer_connection  # noqa: E402
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection  # noqa: E402

with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn:
    rows = conn.execute("""SELECT c.control_id::text AS cid, c.revision, c.payload
        FROM pipeline_runtime_control_revision c
        WHERE c.org_id='org-org' AND c.project_id='dev-project' AND c.control_id::text IN
          (SELECT DISTINCT ON (b.schedule_id) b.control_id::text FROM pipeline_schedule_control_binding b
           WHERE b.org_id='org-org' AND b.project_id='dev-project' AND b.schedule_id LIKE 'sch-p%'
           ORDER BY b.schedule_id, b.created_at DESC)""").fetchall()
    print("latest controls:", len(rows))
    pairs = set()
    for r in rows:
        s = json.dumps(r["payload"])
        for m in re.finditer(
            r'"(policyRef|budgetRef|quotaRef|runtimePolicyRef|governanceRef|modelRouteRef)"\s*:\s*\{[^{}]*?"revision"\s*:\s*"?(\d+)"?\s*[,}]',
            s,
        ):
            pairs.add((m.group(1), int(m.group(2))))
        for m in re.finditer(r'"revision"\s*:\s*"?(\d+)"?\s*,\s*"resourceId"\s*:\s*"([^"]+)"', s):
            rid = m.group(2)
            if any(k in rid for k in ("policy", "budget", "quota", "route")):
                pairs.add((rid[:52], int(m.group(1))))
    for p in sorted(pairs, key=str):
        print(" ", p)
    # runtime policy head (renewal pushed rev12?)
    row = conn.execute("""SELECT policy_id, revision, body->'settings'->>'kind' AS kind,
        body->'settings'->'effectiveFrom' AS eff_from, body->'settings'->'effectiveUntil' AS eff_until
        FROM aip_model_governance_policy_revision
        WHERE org_id='org-org' AND project_id='dev-project' ORDER BY revision DESC LIMIT 3""").fetchall()
    for r in row:
        print("policy head:", dict(r))
