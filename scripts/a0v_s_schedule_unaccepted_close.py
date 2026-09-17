#!/usr/bin/env python3
"""Close S's proven pre-target schedule initialization without business acceptance."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/schedule-closure"
OCCURRENCE = "3c927751-b91a-53d0-8a42-7c5223ea109d"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
KEY = "a0v-s-baseline-pre-target-close-20260917"


def _storage():
    import a0v_controlled_source_claim_deploy as storage
    return storage


def _write(name: str, value: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(name: str) -> dict:
    path = STATE / f"{name}.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} proof required")
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot(conn) -> dict:
    row = conn.execute("""SELECT o.occurrence_id,o.status,o.receipt_ref,o.trigger_source,o.operation_id,
          o.policy_id,o.policy_revision,o.policy_hash,o.installation_id,o.generation,o.execution_epoch,
          a.status AS attempt_status,a.receipt_ref AS attempt_receipt,a.target_idempotency_key,a.claim_until,
          c.receipt_id AS control_receipt_id,c.content_hash AS control_content_hash,
          (SELECT count(*) FROM ecommerce_growth_runtime_command_receipt r
            WHERE r.org_id=o.org_id AND r.project_id=o.project_id
              AND r.operation_id='ecommerce_growth_analysis_advance'
              AND r.idempotency_key=a.target_idempotency_key) AS target_receipts,
          (SELECT count(*) FROM ecommerce_investigation_run r
            WHERE r.org_id=o.org_id AND r.project_id=o.project_id
              AND (r.trigger_key=a.target_idempotency_key OR r.run_id='analysis-'||substr(encode(
                sha256(convert_to(o.org_id||chr(31)||o.project_id||chr(31)||a.target_idempotency_key,'UTF8')),
                'hex'),1,32))) AS target_runs
        FROM automation_occurrence o
        JOIN automation_occurrence_dispatch_attempt a USING(org_id,project_id,occurrence_id)
        JOIN ecommerce_schedule_policy_control_receipt c ON c.org_id=o.org_id AND c.project_id=o.project_id
          AND c.schedule_policy_id=o.policy_id AND c.policy_revision=o.policy_revision
        WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.occurrence_id=%s""",
        (OCCURRENCE,)).fetchone()
    if row is None:
        raise RuntimeError("exact held schedule occurrence required")
    result = dict(row)
    result["occurrence_id"] = str(result["occurrence_id"])
    result["installation_id"] = str(result["installation_id"])
    result["generation"] = str(result["generation"])
    result["control_receipt_id"] = str(result["control_receipt_id"])
    return result


def prepare() -> dict:
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        row = _snapshot(conn)
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        canary = conn.execute("SELECT count(*) AS n FROM ecommerce_unaccepted_analysis_closure_receipt "
                              "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    if (
        version != "a0v_082" or row["status"] != "needs_attention"
        or row["receipt_ref"] is not None or row["trigger_source"] != "schedule"
        or row["operation_id"] != "ecommerce_growth_schedule_trigger"
        or row["attempt_status"] != "unknown" or row["attempt_receipt"] is not None
        or row["target_receipts"] != 0 or row["target_runs"] != 0 or canary != 0
    ):
        raise RuntimeError("proven pre-target S schedule failure required")
    request = {
        "schemaVersion": "aos.ecommerce.unaccepted-schedule-analysis-closure/v1",
        "occurrenceId": OCCURRENCE,
        "scheduleControlReceiptId": row["control_receipt_id"],
        "scheduleControlContentHash": row["control_content_hash"],
        "idempotencyKey": KEY,
    }
    result = {"outcome": "S_BASELINE_PRE_TARGET_CLOSURE_PREPARED", "actor": ACTOR,
              "request": request, "before": row, "preparedAt": datetime.now(UTC).isoformat(),
              "businessAccepted": False, "externalEffects": 0}
    _write("prepare", result)
    return result


def apply() -> dict:
    import a0v_s_successor_business as current
    current.setup()
    proof = _load("prepare")
    if proof.get("actor") != ACTOR or proof.get("request", {}).get("occurrenceId") != OCCURRENCE:
        raise RuntimeError("frozen schedule closure proof differs")
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.ecommerce_unaccepted_analysis_closure import (
        UnacceptedScheduleAnalysisClosureRequest,
        UnacceptedScheduleAnalysisClosureService,
    )
    from aos_api.tenant_scope import TenantScope
    request = UnacceptedScheduleAnalysisClosureRequest.model_validate(proof["request"])
    receipt = UnacceptedScheduleAnalysisClosureService(connect=registration_connection).close(
        scope=TenantScope("org-org", "dev-project"), request=request, actor=ACTOR,
    )
    result = {"outcome": "S_BASELINE_PRE_TARGET_CLOSED_UNACCEPTED", "receipt": receipt,
              "businessAccepted": False, "externalEffects": 0}
    _write("apply", result)
    return result


def audit() -> dict:
    proof = _load("apply")
    storage = _storage()
    with storage.connect(storage.MAIN) as conn:
        row = _snapshot(conn)
        closure = conn.execute("""SELECT authority_data,content_hash FROM ecommerce_unaccepted_analysis_closure_receipt
          WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""", (KEY,)).fetchone()
        canary = conn.execute("SELECT count(*) AS n FROM ecommerce_unaccepted_analysis_closure_receipt "
                              "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    if (
        row["status"] != "cancelled" or row["attempt_status"] != "closed_unaccepted"
        or row["receipt_ref"] is not None or row["attempt_receipt"] is not None
        or row["target_receipts"] != 0 or row["target_runs"] != 0
        or closure is None or closure["content_hash"] != proof["receipt"]["contentHash"] or canary != 0
    ):
        raise RuntimeError("schedule closure terminal audit differs")
    result = {"outcome": "S_BASELINE_PRE_TARGET_CLOSURE_GREEN", "current": row,
              "closureReceipt": {"receiptId": proof["receipt"]["receiptId"],
                                 "contentHash": closure["content_hash"]},
              "businessAccepted": False, "externalEffects": 0, "canaryClosures": canary}
    _write("audit", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "audit"))
    args = parser.parse_args()
    print(json.dumps(globals()[args.phase](), ensure_ascii=False, sort_keys=True, default=str))
