#!/usr/bin/env python3
"""W4 read-only probe: rollback dry-run of enable on definition 268 via the
canonical snapshot-schedule service API (same channel the S wave used)."""
import json
import os
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
    "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(
        ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bn-registration-credentials/registration-main-identity.json"),
})
sys.path.insert(0, "services/aos-api")

from aos_api.asset_registry.control_wiring import build_runtime_control_plane  # noqa: E402
from aos_api.ecommerce_growth_registration_connection import registration_connection  # noqa: E402
from aos_api.extension_runtime.consumer_connection import consumer_connection  # noqa: E402
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

DEFINITION = "cb0dba8c-803f-5caf-8011-b763d349f2ba"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
EXPECTED_REV = 268
SCOPE = TenantScope("org-org", "dev-project")

# facts via worker connection
with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as rconn:
    row = rconn.execute("""SELECT body FROM pipeline_snapshot_schedule_definition_revision
        WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s""",
        ("org-org", "dev-project", DEFINITION, EXPECTED_REV)).fetchone()
    body = row["body"]
    print("def268 state:", body.get("state"), "| cron:", body.get("cron"), "| tz:", body.get("timezone"))
    print("def268 policyRef:", json.dumps(body.get("policyRef"), ensure_ascii=False)[:220])
    head = rconn.execute("""SELECT revision, state, content_hash FROM pipeline_snapshot_schedule_definition_head
        WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
        ("org-org", "dev-project", DEFINITION)).fetchone()
    print("head:", dict(head))

plane = build_runtime_control_plane(registration_connect=registration_connection)
service = plane.pipeline_control_factory.build_snapshot_schedule(SCOPE, source_controls=True)

expected_ref = dict(
    resourceType="SnapshotScheduleDefinitionRevision",
    resourceId="snapshot-schedule-" + DEFINITION,
    revision=EXPECTED_REV,
    contentHash=head["content_hash"])

print("--- enable dry-run (service API, rollback) ---")
with registration_connection() as base:
    from contextlib import contextmanager

    @contextmanager
    def _txn():
        with base.transaction():
            # adopt runtime identity inside this tx
            base.execute("SET LOCAL ROLE aos_runtime")
            base.execute("SELECT set_config('aos.org_id','org-org',true)")
            base.execute("SELECT set_config('aos.project_id','dev-project',true)")
            yield base

    try:
        with _txn() as conn:
            result = service.transition(
                definition_id=DEFINITION, actor=ACTOR, intent="enable",
                expected_ref=expected_ref,
                idempotency_key="w4-enable-dryrun-20260923-rollback-only")
            print("ENABLE DRYRUN OK:", json.dumps(result, ensure_ascii=False, default=str)[:500])
    except Exception as exc:
        print("ENABLE DRYRUN FAIL:", type(exc).__name__, "|", str(exc)[:400])
