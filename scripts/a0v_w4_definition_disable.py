#!/usr/bin/env python3
"""W4 step 6a: disable definition 446cc1ae to begin stalled-group convergence.

The 12-run group 06fa5e56 cannot complete: DR generation c78b2e2e resource
leases were released after the host process was killed (orphan lease reclaim
fenced the binding), and every completion channel requires an admitted binding.
The sanctioned exit is the W3-proven stalled-group closure template:

  1. disable definition (this script) -> 12 schedules flip disabled
  2. after started_at+24h: stalled-group close (12 runs -> failed with effects)
  3. retire definition, rebuild on the next successor installation
  4. enable -> natural dispatch -> 12/12 succeeded

Channels: inspect (read-only) / disable (single transition, idempotent).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-definition-disable"
DEFINITION = "446cc1ae-fa5b-406a-9446-d32104126dda"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
KEY = "a0v-w4-dq-definition-disable-20260923"
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


def _service():
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.tenant_scope import TenantScope
    plane = build_runtime_control_plane(registration_connect=registration_connection)
    return plane.pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)


def _head_ref(definition_id=DEFINITION):
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn:
        row = conn.execute("""SELECT revision, state, content_hash FROM pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
            ("org-org", "dev-project", definition_id)).fetchone()
    if row is None:
        return None
    return dict(revision=row["revision"], state=row["state"],
                ref=dict(resourceType="SnapshotScheduleDefinitionRevision",
                         resourceId="snapshot-schedule-" + definition_id,
                         revision=row["revision"], contentHash=row["content_hash"]))


def inspect():
    _configure()
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    head = _head_ref()
    with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn:
        runs = conn.execute("""SELECT count(*) FILTER (WHERE r.status='running') AS running,
            count(*) AS total, min(r.started_at) AS earliest
            FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
              ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s""",
            ("org-org", "dev-project", "06fa5e56-1ea7-5d08-aa6e-780f58df5ca7")).fetchone()
        schedules = conn.execute("""SELECT count(*) FILTER (WHERE s.enabled) AS enabled_count
            FROM meta_schedule s JOIN pipeline_snapshot_schedule_member m
              ON (m.org_id,m.project_id,m.schedule_id)=(s.org_id,s.project_id,s.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s""",
            ("org-org", "dev-project", "06fa5e56-1ea7-5d08-aa6e-780f58df5ca7")).fetchone()
    import datetime
    earliest = runs["earliest"]
    stale_after = (earliest + datetime.timedelta(hours=24)) if earliest else None
    return {"outcome": "W4_DEFINITION_DISABLE_INSPECT", "head": head,
            "groupRuns": dict(runs), "groupSchedules": dict(schedules),
            "stalledCloseEligibleAfter": stale_after.isoformat() if stale_after else None}


def disable():
    _configure()
    service = _service()
    head = _head_ref()
    if head is None:
        raise RuntimeError("definition head unavailable")
    if head["state"] == "disabled":
        return {"outcome": "W4_DEFINITION_ALREADY_DISABLED", "head": head}
    if head["state"] != "enabled":
        raise RuntimeError(f"definition not enabled: {head}")
    result = service.transition(definition_id=DEFINITION, actor=ACTOR, intent="disable",
        expected_ref=head["ref"], idempotency_key=f"{KEY}-v1")
    _write("disable", {"definition": result})
    return {"outcome": "W4_DEFINITION_DISABLED", "definition": result}


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("inspect", "disable"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
