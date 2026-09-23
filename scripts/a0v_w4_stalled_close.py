#!/usr/bin/env python3
"""Close the W4 stalled twelve-run snapshot group under audited maintenance authority.

Adapted from the W3-proven template (a0v_w3_stalled_group_close.py) for the
group dispatched at 02:39:44 UTC 2026-09-23 whose executor was killed mid-run
(orphan lease reclaim fenced the DR binding; every completion channel requires
an admitted binding, so the runs can never start).

Phases:
  prepare — freeze read-only proof that group 06fa5e56 matches the stalled-group
            closure preconditions (12 running/never-started runs, schedules
            disabled, definition head disabled, started_at older than 24h,
            effects recorded). Fails closed until 2026-09-24T02:39:44Z.
  apply   — call pipeline_snapshot_stalled_group_close_a0v_091 via the trusted
            service; runs terminalize to failed/STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS.
  audit   — read-only verification: 12 runs terminal, receipt matches, dispatch
            inspect no longer reports the group as pending.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-stalled-group-closure"
GROUP = "06fa5e56-1ea7-5d08-aa6e-780f58df5ca7"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
KEY = "a0v-w4-stalled-group-closure-20260924"
REASON = "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS"
ELIGIBLE_AFTER = "2026-09-24T02:39:44.133380+00:00"


def _configure():
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(
            ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bm-runtime-credentials/runtime-host-identities.json"),
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(
            ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bn-registration-credentials/registration-main-identity.json"),
        "AOS_BUNDLE_ROOT": str(
            ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bn-canonical-alias-registry/signed-bundles"),
    })


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


def _load(name):
    path = STATE / f"{name}.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} proof required")
    return json.loads(path.read_text(encoding="utf-8"))


def _storage():
    _configure()
    import a0v_controlled_source_claim_deploy as storage
    return storage


def _survey(conn):
    row = conn.execute("""SELECT c.request#>'{definitionRef}' AS original_ref,
          jsonb_build_object('resourceType','SnapshotScheduleDefinitionRevision',
            'resourceId','snapshot-schedule-'||h.definition_id::text,
            'revision',h.revision,'contentHash',h.content_hash) AS current_ref,
          h.state,h.installation_id,h.generation,
          count(*) AS members,
          count(*) FILTER(WHERE r.status='running' AND r.finished_at IS NULL
            AND r.executor_id='' AND NOT r.executor_stopped AND r.rows_written=0
            AND r.error_code='' AND r.error_message='' AND NOT s.enabled) AS stalled,
          count(*) FILTER(WHERE r.status='failed' AND r.finished_at IS NOT NULL
            AND r.executor_id='pipeline-live-v1' AND r.executor_stopped
            AND r.error_code=%s) AS closed,
          min(r.started_at) FILTER(WHERE r.status='running') AS earliest_started
        FROM pipeline_snapshot_schedule_claim c
        JOIN pipeline_snapshot_schedule_member m USING(org_id,project_id,group_id)
        JOIN meta_schedule_run r ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
        JOIN meta_schedule s ON (s.org_id,s.project_id,s.id)=(m.org_id,m.project_id,m.schedule_id)
        JOIN pipeline_snapshot_schedule_definition_head h ON h.org_id=c.org_id AND h.project_id=c.project_id
          AND 'snapshot-schedule-'||h.definition_id::text=c.request#>>'{definitionRef,resourceId}'
        WHERE c.org_id='org-org' AND c.project_id='dev-project' AND c.group_id=%s
        GROUP BY c.request,h.definition_id,h.revision,h.content_hash,h.state,h.installation_id,h.generation""",
        (REASON, GROUP)).fetchone()
    effects = {}
    effects["groupClaims"] = conn.execute("SELECT count(*) n FROM pipeline_snapshot_group_claim "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    effects["groupInputs"] = conn.execute("SELECT count(*) n FROM pipeline_snapshot_group_input "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    effects["groupMembers"] = conn.execute("SELECT count(*) n FROM pipeline_snapshot_group_member "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    for key, table in (("sourceClaims", "pipeline_controlled_source_claim"),
                       ("ingressCommands", "ecommerce_ingress_command"),
                       ("derivedCommands", "ecommerce_ingress_derived_command"),
                       ("datasetReceipts", "ecommerce_ingress_dataset_receipt")):
        effects[key] = conn.execute(f"""SELECT count(*) n FROM {table} x
          JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(x.org_id,x.project_id,x.run_id)
          WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s""",
          (GROUP,)).fetchone()["n"]
    stalled_receipts = conn.execute(
        "SELECT count(*) n FROM pipeline_snapshot_stalled_group_closure_receipt "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    canary = conn.execute(
        "SELECT count(*) n FROM pipeline_snapshot_stalled_group_closure_receipt "
        "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    return {"group": dict(row) if row else None, "effects": effects,
            "stalledReceipts": stalled_receipts, "canaryReceipts": canary}


def prepare():
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        before = _survey(conn)
        eligible = conn.execute("SELECT %s::timestamptz <= clock_timestamp() AS ok",
            (ELIGIBLE_AFTER,)).fetchone()["ok"]
    group = before["group"] or {}
    if (version != "a0v_091" or not eligible or group.get("state") != "disabled" or group.get("members") != 12
            or group.get("stalled") != 12 or group.get("closed") != 0
            or before["stalledReceipts"] != 0 or before["canaryReceipts"] != 0):
        raise RuntimeError(f"exact stalled disabled group required (eligible={eligible}, survey={before})")
    request = {
        "schemaVersion": "aos.pipeline-snapshot.stalled-group-closure/v1",
        "groupId": GROUP, "originalDefinitionRef": group["original_ref"],
        "currentDisabledDefinitionRef": group["current_ref"], "reasonCode": REASON,
        "idempotencyKey": KEY,
    }
    result = {"outcome": "W4_STALLED_GROUP_CLOSURE_PREPARED", "actor": ACTOR,
              "request": request, "before": before, "businessAccepted": False, "externalEffects": 0}
    _write("prepare", result)
    return result


def apply():
    _configure()
    proof = _load("prepare")
    if proof.get("actor") != ACTOR or proof.get("request", {}).get("groupId") != GROUP:
        raise RuntimeError("frozen stalled closure proof differs")
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.pipeline_snapshot_stalled_group_closure import (
        StalledSnapshotGroupClosureRequest, StalledSnapshotGroupClosureService,
    )
    from aos_api.tenant_scope import TenantScope
    request = StalledSnapshotGroupClosureRequest.model_validate(proof["request"])
    receipt = StalledSnapshotGroupClosureService(connect=registration_connection).close(
        scope=TenantScope("org-org", "dev-project"), request=request, actor=ACTOR,
    )
    result = {"outcome": "W4_STALLED_GROUP_CLOSED", "receipt": receipt,
              "businessAccepted": False, "externalEffects": 0}
    _write("apply", result)
    return result


def audit():
    proof = _load("apply")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        current = _survey(conn)
        receipt = conn.execute("""SELECT receipt_id,content_hash,authority_data
          FROM pipeline_snapshot_stalled_group_closure_receipt
          WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""", (KEY,)).fetchone()
    group = current["group"] or {}
    if (group.get("stalled") != 0 or group.get("closed") != 12
            or receipt is None or str(receipt["receipt_id"]) != proof["receipt"]["receiptId"]
            or receipt["content_hash"] != proof["receipt"]["contentHash"]
            or receipt["authority_data"].get("businessAccepted") is not False
            or current["canaryReceipts"] != 0):
        raise RuntimeError("stalled closure terminal audit differs")
    result = {"outcome": "W4_STALLED_GROUP_CLOSURE_GREEN", "current": current,
              "closureReceipt": {"receiptId": str(receipt["receipt_id"]),
                                 "contentHash": receipt["content_hash"]},
              "businessAccepted": False, "externalEffects": 0,
              "canaryClosures": current["canaryReceipts"]}
    _write("audit", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
