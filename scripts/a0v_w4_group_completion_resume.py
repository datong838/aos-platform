"""W4 step 6: resume the interrupted whole-group execution for the pending group.

The old aos-api process was terminated between claim COMMIT and completion.
Facts already durable:
  - schedule claim 06fa5e56... committed (12 runs running)
  - group input manifest saved (read completed 02:40:12 UTC)
The original Runtime is idempotent across exactly these facts:
  - claim replays previous identical request
  - prepare replays saved manifest inputs
  - complete advances retirement/projection and finishes runs
This script re-invokes the original runtime with the exact original
claim parameters. No new group is created.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-definition-rebuild"
GROUP_ID = "06fa5e56-1ea7-5d08-aa6e-780f58df5ca7"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
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


def _plane():
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection())


def resume():
    _configure()
    from aos_api.ecom_consistency_store import EcomConsistencyStore
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.phase5_pipeline_engine import get_engine
    from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
    from aos_api.pipeline_snapshot_schedule_runtime import PipelineSnapshotScheduleRuntime
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope("org-org", "dev-project")
    services = _plane().pipeline_control_factory.build(scope)
    engine = get_engine()
    runtime = PipelineSnapshotScheduleRuntime(
        claims=services.claims,
        store=EcomConsistencyStore(engine),
        connect=runtime_worker_connection,
        eng=engine,
    )
    workers = dict(org_id="org-org", project_id="dev-project")

    with consumer_connection(runtime_worker_connection, workers) as conn:
        row = conn.execute("""SELECT group_id, actor, scheduled_for, trigger, request
            FROM pipeline_snapshot_schedule_claim
            WHERE org_id=%s AND project_id=%s AND group_id=%s""",
            (*scope.key, GROUP_ID)).fetchone()
        if row is None:
            raise RuntimeError("original claim not found for pending group")
        definition_ref = row["request"].get("definitionRef")
        scheduled_for = row["scheduled_for"]
        actor = row["actor"]
        trigger = row["trigger"]

    result = runtime.execute(
        scope=scope,
        definition_ref=PipelineExactRef.model_validate(definition_ref),
        group_id=GROUP_ID,
        actor=actor,
        scheduled_for=scheduled_for,
        trigger=trigger,
    )
    _write("group-resume", dict(result))
    return result


def verify():
    _configure()
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

    workers = dict(org_id="org-org", project_id="dev-project")
    with consumer_connection(runtime_worker_connection, workers) as conn:
        rows = conn.execute("""SELECT status, count(*) AS n
            FROM meta_schedule_run WHERE org_id='org-org' AND project_id='dev-project'
              AND started_at > '2026-09-23 02:30:00+00'
            GROUP BY status ORDER BY status""").fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        claim = conn.execute("""SELECT group_id FROM pipeline_snapshot_schedule_claim
            WHERE org_id='org-org' AND project_id='dev-project'
            ORDER BY created_at DESC LIMIT 1""").fetchone()
        relationships = conn.execute("""SELECT count(*) AS n FROM pipeline_snapshot_group_relationship
            WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s""",
            (GROUP_ID,)).fetchone()
    return {
        "outcome": "W4_GROUP_RESUME_VERIFY",
        "runStatusCounts": counts,
        "expected": {"succeeded": 12},
        "latestClaimGroup": str(claim["group_id"]),
        "groupRelationships": relationships["n"],
    }


def main():
    parser = argparse.ArgumentParser(description="W4 resume interrupted whole-group execution")
    parser.add_argument("phase", choices=["resume", "verify"])
    args = parser.parse_args()
    if args.phase == "resume":
        result = resume()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
