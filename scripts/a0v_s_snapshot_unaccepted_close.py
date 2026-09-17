#!/usr/bin/env python3
"""Close the proven pre-source twelve-source schedule group without acceptance."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/snapshot-group-closure"
GROUP = "f8d6b5af-f7a3-5f15-88ee-6432012f9537"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
KEY = "a0v-s-snapshot-group-pre-source-close-20260917"
REASON = "SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM"


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
    import a0v_controlled_source_claim_deploy as storage
    return storage


def _snapshot(conn):
    row = conn.execute("""SELECT c.request#>'{definitionRef}' AS original_ref,
          jsonb_build_object('resourceType','SnapshotScheduleDefinitionRevision',
            'resourceId','snapshot-schedule-'||h.definition_id::text,
            'revision',h.revision,'contentHash',h.content_hash) AS current_ref,
          h.state,h.installation_id,h.generation,
          count(*) AS members,
          count(*) FILTER(WHERE r.status='running' AND r.finished_at IS NULL
            AND r.executor_id='' AND NOT r.executor_stopped AND r.rows_written=0
            AND r.error_code='' AND r.error_message='' AND NOT s.enabled) AS running,
          count(*) FILTER(WHERE r.status='failed' AND r.finished_at IS NOT NULL
            AND r.executor_id='pipeline-live-v1' AND r.executor_stopped
            AND r.error_code=%s) AS closed
        FROM pipeline_snapshot_schedule_claim c
        JOIN pipeline_snapshot_schedule_member m USING(org_id,project_id,group_id)
        JOIN meta_schedule_run r ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
        JOIN meta_schedule s ON (s.org_id,s.project_id,s.id)=(m.org_id,m.project_id,m.schedule_id)
        JOIN pipeline_snapshot_schedule_definition_head h ON h.org_id=c.org_id AND h.project_id=c.project_id
          AND 'snapshot-schedule-'||h.definition_id::text=c.request#>>'{definitionRef,resourceId}'
        WHERE c.org_id='org-org' AND c.project_id='dev-project' AND c.group_id=%s
        GROUP BY c.request,h.definition_id,h.revision,h.content_hash,h.state,h.installation_id,h.generation""",
        (REASON, GROUP)).fetchone()
    no_effect = {}
    no_effect["groupClaims"] = conn.execute("SELECT count(*) n FROM pipeline_snapshot_group_claim "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    no_effect["groupInputs"] = conn.execute("SELECT count(*) n FROM pipeline_snapshot_group_input "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    no_effect["groupMembers"] = conn.execute("SELECT count(*) n FROM pipeline_snapshot_group_member "
        "WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s", (GROUP,)).fetchone()["n"]
    for key, table in (("sourceClaims", "pipeline_controlled_source_claim"),
                       ("ingressCommands", "ecommerce_ingress_command"),
                       ("derivedCommands", "ecommerce_ingress_derived_command"),
                       ("datasetReceipts", "ecommerce_ingress_dataset_receipt")):
        no_effect[key] = conn.execute(f"""SELECT count(*) n FROM {table} x
          JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(x.org_id,x.project_id,x.run_id)
          WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s""",
          (GROUP,)).fetchone()["n"]
    return {"group": dict(row) if row else None, "noEffect": no_effect}


def prepare():
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        before = _snapshot(conn)
        canary = conn.execute("SELECT count(*) n FROM pipeline_snapshot_unaccepted_group_closure_receipt "
            "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    group = before["group"] or {}
    if (version != "a0v_083" or group.get("state") != "disabled" or group.get("members") != 12
            or group.get("running") != 12 or group.get("closed") != 0
            or any(before["noEffect"].values()) or canary != 0):
        raise RuntimeError("exact disabled no-effect group required")
    request = {
        "schemaVersion": "aos.pipeline-snapshot.unaccepted-group-closure/v1",
        "groupId": GROUP, "originalDefinitionRef": group["original_ref"],
        "currentDisabledDefinitionRef": group["current_ref"], "reasonCode": REASON,
        "idempotencyKey": KEY,
    }
    result = {"outcome": "S_SNAPSHOT_GROUP_UNACCEPTED_CLOSURE_PREPARED", "actor": ACTOR,
              "request": request, "before": before, "businessAccepted": False, "externalEffects": 0}
    _write("prepare", result)
    return result


def apply():
    import a0v_s_successor_business as current
    current.setup()
    proof = _load("prepare")
    if proof.get("actor") != ACTOR or proof.get("request", {}).get("groupId") != GROUP:
        raise RuntimeError("frozen snapshot closure proof differs")
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.pipeline_snapshot_unaccepted_group_closure import (
        UnacceptedSnapshotGroupClosureRequest, UnacceptedSnapshotGroupClosureService,
    )
    from aos_api.tenant_scope import TenantScope
    request = UnacceptedSnapshotGroupClosureRequest.model_validate(proof["request"])
    receipt = UnacceptedSnapshotGroupClosureService(connect=registration_connection).close(
        scope=TenantScope("org-org", "dev-project"), request=request, actor=ACTOR,
    )
    result = {"outcome": "S_SNAPSHOT_GROUP_CLOSED_UNACCEPTED", "receipt": receipt,
              "businessAccepted": False, "externalEffects": 0}
    _write("apply", result)
    return result


def audit():
    proof = _load("apply")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        current = _snapshot(conn)
        receipt = conn.execute("""SELECT receipt_id,content_hash,authority_data
          FROM pipeline_snapshot_unaccepted_group_closure_receipt
          WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""", (KEY,)).fetchone()
        canary = conn.execute("SELECT count(*) n FROM pipeline_snapshot_unaccepted_group_closure_receipt "
            "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    group = current["group"] or {}
    if (group.get("running") != 0 or group.get("closed") != 12 or any(current["noEffect"].values())
            or receipt is None or str(receipt["receipt_id"]) != proof["receipt"]["receiptId"]
            or receipt["content_hash"] != proof["receipt"]["contentHash"]
            or receipt["authority_data"].get("businessAccepted") is not False or canary != 0):
        raise RuntimeError("snapshot closure terminal audit differs")
    result = {"outcome": "S_SNAPSHOT_GROUP_UNACCEPTED_CLOSURE_GREEN", "current": current,
              "closureReceipt": {"receiptId": str(receipt["receipt_id"]),
                                 "contentHash": receipt["content_hash"]},
              "businessAccepted": False, "externalEffects": 0, "canaryClosures": canary}
    _write("audit", result)
    return result


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
