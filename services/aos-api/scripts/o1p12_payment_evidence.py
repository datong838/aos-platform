#!/usr/bin/env python3
"""O1-A/P12 Payment 权威指标链只读证据采集。

业务源和 AOS PostgreSQL 均只读；唯一写入是版本化 JSON 证据文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from aos_api.db import connect
from aos_api.ec_source_adapter import (
    BATCH_READ_SPECS,
    _query_meta_source_props,
)
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
SOURCE_ID = "niushop-qyh"
PAYMENT_OT = "Payment"


def _git_sha(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_snapshot() -> tuple[list[dict], set[str]]:
    props = _query_meta_source_props(SOURCE_ID, SCOPE)
    with JdbcConnectorRuntime(props) as runtime:
        payments = runtime.read_rows("ns_pay", limit=None)
        order_ids = tuple(
            dict.fromkeys(
                str(row.get("relate_id") or "").strip()
                for row in payments
                if str(row.get("relate_id") or "").strip()
            )
        )
        orders = runtime.read_rows_by_values(
            BATCH_READ_SPECS["payment_order_time"], order_ids
        )
    order_create_by_id = {
        str(row["order_id"]): row.get("create_time")
        for row in orders
        if row.get("order_id") is not None
    }
    eligible_ids = {
        f"niushop:1:{row['id']}"
        for row in payments
        if int(row.get("pay_time") or 0) > 0
        and order_create_by_id.get(str(row.get("relate_id") or "")) not in (None, "")
    }
    return payments, eligible_ids


def _pg_snapshot(eligible_ids: set[str]) -> dict:
    with connect(SCOPE) as conn:
        rows = conn.execute(
            """
            SELECT external_id, properties, derived_payload, derived_revision,
                   derived_input_revision, derived_payload_hash
              FROM ecom_object
             WHERE org_id=%s AND workspace_id=%s AND object_type=%s
             ORDER BY external_id
            """,
            (*SCOPE.key, PAYMENT_OT),
        ).fetchall()
        canonical = {str(row["external_id"]): row for row in rows}
        eligible_present = eligible_ids.intersection(canonical)
        eligible_nonnull = {
            external_id
            for external_id in eligible_present
            if canonical[external_id]["derived_payload"].get("pay_duration_min")
            is not None
        }
        negative = {
            external_id
            for external_id in eligible_nonnull
            if float(
                canonical[external_id]["derived_payload"]["pay_duration_min"]
            )
            < 0
        }
        base_leaks = sum(
            1 for row in rows if "pay_duration_min" in (row["properties"] or {})
        )
        receipts = conn.execute(
            """
            SELECT count(*) AS total
              FROM ecom_derived_receipt
             WHERE org_id=%s AND project_id=%s AND object_type=%s
            """,
            (*SCOPE.key, PAYMENT_OT),
        ).fetchone()["total"]
        pending = conn.execute(
            """
            SELECT count(*) AS total
              FROM projection_outbox
             WHERE org_id=%s AND project_id=%s AND projected_at IS NULL
            """,
            SCOPE.key,
        ).fetchone()["total"]
        projected = conn.execute(
            """
            SELECT object_id, props
              FROM obj_instance
             WHERE org_id=%s AND project_id=%s AND object_type=%s
            """,
            (*SCOPE.key, PAYMENT_OT),
        ).fetchall()
        projected_by_id = {str(row["object_id"]): row["props"] for row in projected}
        projected_eligible_nonnull = {
            external_id
            for external_id in eligible_ids.intersection(projected_by_id)
            if projected_by_id[external_id].get("pay_duration_min") is not None
        }
        legacy_aliases = sorted(set(projected_by_id) - set(canonical))

    eligible_total = len(eligible_ids)
    authoritative_nonnull = len(eligible_nonnull)
    projection_nonnull = len(projected_eligible_nonnull)
    return {
        "authoritative_payment_total": len(canonical),
        "eligible_present_in_authority": len(eligible_present),
        "eligible_metric_nonnull": authoritative_nonnull,
        "eligible_metric_rate_pct": round(
            authoritative_nonnull / eligible_total * 100, 2
        )
        if eligible_total
        else None,
        "negative_metric_count": len(negative),
        "base_property_metric_leak_count": base_leaks,
        "derived_receipt_count": int(receipts),
        "projection_pending_count": int(pending),
        "projected_payment_total": len(projected_by_id),
        "projected_eligible_metric_nonnull": projection_nonnull,
        "projected_eligible_metric_rate_pct": round(
            projection_nonnull / eligible_total * 100, 2
        )
        if eligible_total
        else None,
        "legacy_projection_alias_count": len(legacy_aliases),
        "legacy_projection_alias_hash": _canonical_hash(legacy_aliases),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests/d5e/evidence",
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    started_at = datetime.now(timezone.utc)
    payments, eligible_ids = _source_snapshot()
    pg = _pg_snapshot(eligible_ids)
    source_total = len(payments)
    eligible_total = len(eligible_ids)
    pass_payment_chain = (
        source_total > 0
        and eligible_total > 0
        and pg["eligible_present_in_authority"] == eligible_total
        and pg["eligible_metric_nonnull"] == eligible_total
        and pg["projected_eligible_metric_nonnull"] == eligible_total
        and pg["negative_metric_count"] == 0
        and pg["base_property_metric_leak_count"] == 0
        and pg["projection_pending_count"] == 0
    )
    evidence = {
        "gate": "O1-A/P12-Payment-authoritative-metric-chain",
        "status": "PASS" if pass_payment_chain else "RED",
        "overall_d5_status": "BLOCKED",
        "overall_d5_blockers": [
            "O1-D alias migration is not implemented/applied",
            "G17-SPEC and D4-SPEC-SYNC are not PASS",
            "D5-E1 write/canary harness is not implemented",
        ],
        "scope": {"org_id": SCOPE.org_id, "workspace_id": SCOPE.project_id},
        "source": {
            "source_id": SOURCE_ID,
            "payment_total": source_total,
            "eligible_total": eligible_total,
            "eligible_definition": "ns_pay.pay_time > 0 and related ns_order.create_time exists",
            "eligible_identity_hash": _canonical_hash(sorted(eligible_ids)),
        },
        "authority_and_projection": pg,
        "git_sha": _git_sha(repo),
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        "O1-P12_Payment_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + ".json"
    )
    path = args.output_dir / filename
    path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"evidence": str(path), **evidence}, ensure_ascii=False))
    return 0 if pass_payment_chain else 1


if __name__ == "__main__":
    raise SystemExit(main())
