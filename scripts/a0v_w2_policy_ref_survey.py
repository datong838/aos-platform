#!/usr/bin/env python3
"""W2 read-only survey: where do the recovery chain's frozen policy refs point?

After budget renewal pushed the runtime-policy head to rev12, the replay showed
"runtime policy reference is not current and exact". Survey exactly which
revision each layer freezes:
  1. recovery receipt body.policyRef
  2. definition revisions (state column; saved bindings inside body)
  3. group claim record members
  4. current governance heads
No writes; single connection, plain SELECTs.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "aos-api"))

GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
SCOPE_ARGS = dict(org_id="org-org", project_id="dev-project")
CREDENTIAL_FILE = ("/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/"
                   "q-advisor-baseline/bm-runtime-credentials/runtime-host-identities.json")
BUNDLE_ROOT = ("/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/"
               "q-advisor-baseline/bn-canonical-alias-registry/signed-bundles")
TRUST_ROOTS = ("/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/"
               "q-advisor-baseline/bm-trust-root-rotation/signing/trust-roots.json")


def _configure() -> None:
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": CREDENTIAL_FILE,
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_BUNDLE_ROOT": BUNDLE_ROOT,
        "AOS_BUNDLE_TRUST_ROOTS_FILE": TRUST_ROOTS,
    })
    for name in ("AOS_DATABASE_URL", "AOS_EXTENSION_RUNTIME_DATABASE_URL",
                 "AOS_EXTENSION_DIRECTORY_DATABASE_URL"):
        os.environ.pop(name, None)


def brief(ref):
    if not isinstance(ref, dict):
        return str(ref)[:70]
    return f"{str(ref.get('assetType', '?'))[:28]}:{str(ref.get('assetId', '?'))[:40]}@r{ref.get('revision')}"


def main() -> int:
    _configure()
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope("org-org", "dev-project")

    with consumer_connection(runtime_worker_connection, SCOPE_ARGS) as conn:
        out = {}

        # 1. recovery receipt
        receipt = read_recovery_receipt(conn, scope=scope, group_id=GROUP)
        if receipt is None:
            print(json.dumps({"receipt": "MISSING"}, ensure_ascii=False))
            return 2
        out["receipt"] = dict(
            definition_ref=brief(receipt["body"].get("currentDefinitionRef")),
            policy_ref=brief(receipt["body"].get("policyRef")),
            executor=receipt["body"].get("executor"),
            revision=receipt["ref"].get("revision"),
        )

        # 2. definition revisions for this group (definition_id from receipt ref)
        def_ref = receipt["body"].get("currentDefinitionRef") or {}
        def_id = def_ref.get("assetId") or def_ref.get("asset_id") or def_ref.get("id")
        rows = conn.execute(
            """SELECT definition_id, revision, state, body, created_at
                 FROM pipeline_snapshot_schedule_definition_revision
                WHERE org_id=%s AND project_id=%s AND definition_id=%s
                ORDER BY revision DESC LIMIT 3""",
            (*SCOPE_ARGS.values(), def_id)).fetchall()
        defs = []
        for row in rows:
            body = row["body"] or {}
            saved = body.get("savedBindings") or body.get("saved_bindings") or []
            refs = []
            for b in saved[:2]:
                refs.append(brief(b.get("controlRef") or b.get("control_ref")))
            defs.append(dict(revision=row["revision"], state=row["state"],
                             policy_ref=brief(body.get("policyRef")),
                             saved_binding_refs=refs, members=len(saved),
                             created=str(row["created_at"])[:19]))
        out["definitions"] = defs

        head = conn.execute(
            """SELECT revision FROM pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
            (*SCOPE_ARGS.values(), def_id)).fetchone()
        out["definition_head"] = head["revision"] if head else None

        # 3. group claim record
        claim = conn.execute(
            """SELECT record, content_hash, created_at FROM pipeline_snapshot_schedule_claim
                WHERE org_id=%s AND project_id=%s AND group_id=%s""",
            (*SCOPE_ARGS.values(), GROUP)).fetchone()
        if claim is not None:
            record = claim["record"] or {}
            members = record.get("members") or []
            out["claim"] = dict(
                created=str(claim["created_at"])[:19],
                members=len(members),
                member0=dict(schedule=str(members[0].get("scheduleId"))[:18],
                             run=str(members[0].get("runId"))[:8]) if members else None,
            )

        # 4. governance heads
        heads = {}
        for label, sql, args in (
            ("runtime_policy",
             "SELECT current_revision FROM aip_runtime_policy_head WHERE org_id=%s AND project_id=%s AND runtime_policy_id=%s",
             ("a0v-ecommerce-runtime-policy-v1",)),
            ("budget_guess",
             "SELECT policy_id, current_revision FROM aip_model_governance_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind='budget'",
             ()),
        ):
            try:
                row = conn.execute(sql, (*SCOPE_ARGS.values(), *args)).fetchall()
                heads[label] = [dict(id=str(r.get("policy_id") or r.get("runtime_policy_id"))[:44],
                                     rev=r["current_revision"]) for r in row]
            except Exception as exc:
                heads[label] = f"ERR {type(exc).__name__}"
        out["heads"] = heads

        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
