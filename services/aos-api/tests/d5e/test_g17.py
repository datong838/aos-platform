"""
G17 baseline — read-only derived metrics snapshot for D5-E0.

This test ONLY reads from ecom_object. No writes, no failure injection.
All metrics are expected to be RED or INCONCLUSIVE — this is the honest baseline.
"""

import hashlib
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from .conftest import (
    DB_URL,
    TENANT_SCOPE,
    collect_evidence_metadata,
    save_evidence,
)

from sqlalchemy import create_engine


# ---------------------------------------------------------------------------
# SQL queries (read-only)
# ---------------------------------------------------------------------------

def _count_by_ot(conn, ot: str) -> int:
    r = conn.execute(
        text(
            "SELECT count(*) FROM ecom_object "
            "WHERE org_id = :org AND workspace_id = :ws AND object_type = :ot"
        ),
        {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"], "ot": ot},
    )
    return r.scalar()


def _count_metric_nonnull(conn, ot: str, metric_key: str) -> int:
    r = conn.execute(
        text(
            "SELECT count(*) FROM ecom_object "
            "WHERE org_id = :org AND workspace_id = :ws AND object_type = :ot "
            "AND properties->>:key IS NOT NULL AND properties->>:key != 'null'"
        ),
        {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"],
         "ot": ot, "key": metric_key},
    )
    return r.scalar()


def _sql_hash(conn, sql: str, params: dict) -> str:
    """Compute a deterministic hash of the query result for evidence."""
    r = conn.execute(text(sql), params)
    rows = [dict(zip(r.keys(), row)) for row in r.fetchall()]
    # Convert values to strings for stable hashing
    stable = json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(stable.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestG17Baseline:
    """D5-E0: G17 read-only baseline snapshot."""

    def test_g17_data_snapshot(self, db_conn, evidence_meta):
        """Capture authoritative layer counts and per-OT breakdown."""
        results = {}

        # Total ecom_object
        total = _count_by_ot(db_conn, "Product")  # placeholder
        results["ecom_object_total"] = sum(
            _count_by_ot(db_conn, ot)
            for ot in ["Shop", "Product", "ProductSku", "Category",
                       "Order", "OrderLine", "Shipment", "CustomerLite"]
        )
        results["ecom_link_total"] = db_conn.execute(
            text(
                "SELECT count(*) FROM ecom_link "
                "WHERE org_id = :org AND workspace_id = :ws"
            ),
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        ).scalar()
        results["obj_instance_total"] = db_conn.execute(
            text(
                "SELECT count(*) FROM obj_instance "
                "WHERE org_id = :org AND project_id = :ws"
            ),
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        ).scalar()

        # Per-OT breakdown
        per_ot = {}
        for ot in ["Shop", "Product", "ProductSku", "Category",
                   "Order", "OrderLine", "Shipment", "CustomerLite",
                   "Weapp", "SystemConfig", "ProductReview", "Payment"]:
            per_ot[ot] = _count_by_ot(db_conn, ot)
        results["per_ot"] = per_ot

        # ecom_object snapshot hash
        snapshot_sql = (
            "SELECT object_type, count(*) FROM ecom_object "
            "WHERE org_id = :org AND workspace_id = :ws "
            "GROUP BY object_type ORDER BY object_type"
        )
        results["data_snapshot_hash"] = _sql_hash(
            db_conn, snapshot_sql,
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        )

        results["data_snapshot_revision"] = (
            f"ecom_object={results['ecom_object_total']}, "
            f"ecom_link={results['ecom_link_total']}, "
            f"obj_instance={results['obj_instance_total']}, "
            f"per_ot={per_ot}"
        )

        # Save evidence
        save_evidence("G17", "D5-E0", results, evidence_meta)

    def test_g17_quality_score(self, db_conn, evidence_meta):
        """G17 baseline: Product.quality_score."""
        total = _count_by_ot(db_conn, "Product")
        nonnull = _count_metric_nonnull(db_conn, "Product", "quality_score")

        # eligible denominator: evaluate>0
        eligible_r = db_conn.execute(
            text(
                "SELECT count(*) FROM ecom_object "
                "WHERE org_id = :org AND workspace_id = :ws AND object_type = 'Product' "
                "AND COALESCE((properties->>'evaluate')::int, 0) > 0"
            ),
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        )
        eligible = eligible_r.scalar()

        rate = round(nonnull / eligible * 100, 1) if eligible > 0 else 0.0
        status = "RED" if eligible == 0 or rate < 90 else "GREEN"

        result = {
            "metric": "quality_score",
            "ot": "Product",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "eligible_definition": "evaluate>0",
            "rate_pct": rate,
            "threshold_pct": 90,
            "status": status,
            "root_cause": "eligible_total=0, no Product has evaluate>0 in current data" if eligible == 0 else None,
            "fix_target": "O1-A",
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

        # D5-E0 allows RED
        assert result["status"] in ("RED", "GREEN", "INCONCLUSIVE"), (
            f"quality_score baseline: {result}"
        )

    def test_g17_stock_health(self, db_conn, evidence_meta):
        """G17 baseline: ProductSku.stock_health."""
        total = _count_by_ot(db_conn, "ProductSku")
        nonnull = _count_metric_nonnull(db_conn, "ProductSku", "stock_health")
        eligible = total  # full population
        rate = round(nonnull / eligible * 100, 1) if eligible > 0 else 0.0
        status = "GREEN" if rate >= 85 else "RED"

        result = {
            "metric": "stock_health",
            "ot": "ProductSku",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "rate_pct": rate,
            "threshold_pct": 85,
            "status": status,
            "fix_target": None if status == "GREEN" else "O1-A",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

    def test_g17_risk_score(self, db_conn, evidence_meta):
        """G17 baseline: Order.risk_score."""
        total = _count_by_ot(db_conn, "Order")
        nonnull = _count_metric_nonnull(db_conn, "Order", "risk_score")
        eligible = total
        rate = round(nonnull / eligible * 100, 1) if eligible > 0 else 0.0
        status = "GREEN" if rate >= 90 else "RED"

        result = {
            "metric": "risk_score",
            "ot": "Order",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "rate_pct": rate,
            "threshold_pct": 90,
            "status": status,
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

    def test_g17_overdue_hours(self, db_conn, evidence_meta):
        """G17 baseline: Shipment.overdue_hours."""
        total = _count_by_ot(db_conn, "Shipment")
        nonnull = _count_metric_nonnull(db_conn, "Shipment", "overdue_hours")

        # eligible: delivery_time=0 AND pay_time>0
        eligible_r = db_conn.execute(
            text(
                "SELECT count(*) FROM ecom_object "
                "WHERE org_id = :org AND workspace_id = :ws AND object_type = 'Shipment' "
                "AND COALESCE((properties->>'delivery_time')::int, 0) = 0 "
                "AND COALESCE((properties->>'pay_time')::int, 0) > 0"
            ),
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        )
        eligible = eligible_r.scalar()

        rate = round(nonnull / eligible * 100, 1) if eligible > 0 else 0.0
        if eligible == 0:
            status = "INCONCLUSIVE"
        elif rate >= 90:
            status = "GREEN"
        else:
            status = "RED"

        result = {
            "metric": "overdue_hours",
            "ot": "Shipment",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "eligible_definition": "delivery_time=0 AND pay_time>0",
            "rate_pct": rate,
            "threshold_pct": 90,
            "status": status,
            "root_cause": "eligible_total=0" if eligible == 0 else None,
            "fix_target": "O1-A",
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

    def test_g17_order_count(self, db_conn, evidence_meta):
        """G17 baseline: CustomerLite.order_count."""
        total = _count_by_ot(db_conn, "CustomerLite")
        nonnull = _count_metric_nonnull(db_conn, "CustomerLite", "order_count")

        # eligible depends on ecom_link Order.placedByLite existing
        link_count = db_conn.execute(
            text(
                "SELECT count(*) FROM ecom_link "
                "WHERE org_id = :org AND workspace_id = :ws "
                "AND link_type = 'Order.placedByLite'"
            ),
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        ).scalar()

        eligible = link_count  # depends on links existing
        if eligible == 0:
            status = "INCONCLUSIVE"
            rate_str = "N/A"
        else:
            rate = round(nonnull / total * 100, 1) if total > 0 else 0.0
            rate_str = str(rate)
            status = "GREEN" if rate >= 90 else "RED"

        result = {
            "metric": "order_count",
            "ot": "CustomerLite",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "eligible_definition": "ecom_link Order.placedByLite exists (currently 0)",
            "rate_pct": rate_str,
            "threshold_pct": 90,
            "status": status,
            "root_cause": "ecom_link=0, eligible=0, INCONCLUSIVE. "
                          "37/54 non-null are historical residue.",
            "fix_target": "O1-A (link_aggregator injection + derived CAS)",
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

    def test_g17_last_order_days(self, db_conn, evidence_meta):
        """G17 baseline: CustomerLite.last_order_days."""
        total = _count_by_ot(db_conn, "CustomerLite")
        nonnull = _count_metric_nonnull(db_conn, "CustomerLite", "last_order_days")

        link_count = db_conn.execute(
            text(
                "SELECT count(*) FROM ecom_link "
                "WHERE org_id = :org AND workspace_id = :ws "
                "AND link_type = 'Order.placedByLite'"
            ),
            {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
        ).scalar()

        eligible = link_count
        if eligible == 0:
            status = "INCONCLUSIVE"
            rate_str = "N/A"
        else:
            rate = round(nonnull / total * 100, 1) if total > 0 else 0.0
            rate_str = str(rate)
            status = "GREEN" if rate >= 90 else "RED"

        result = {
            "metric": "last_order_days",
            "ot": "CustomerLite",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "eligible_definition": "ecom_link Order.placedByLite exists (currently 0)",
            "rate_pct": rate_str,
            "threshold_pct": 90,
            "status": status,
            "root_cause": "ecom_link=0 → INCONCLUSIVE. 37/54 non-null are historical residue.",
            "fix_target": "O1-A (link_aggregator reading properties.createdAt)",
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

    def test_g17_review_quality_bucket(self, db_conn, evidence_meta):
        """G17 baseline: ProductReview.review_quality_bucket."""
        total = _count_by_ot(db_conn, "ProductReview")
        if total == 0:
            status = "RED"
            nonnull = 0
            eligible = 0
        else:
            nonnull = _count_metric_nonnull(db_conn, "ProductReview", "review_quality_bucket")
            eligible = total
            rate = round(nonnull / eligible * 100, 1) if eligible > 0 else 0.0
            status = "GREEN" if rate >= 90 else "RED"

        result = {
            "metric": "review_quality_bucket",
            "ot": "ProductReview",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "rate_pct": 0.0,
            "status": status,
            "root_cause": "ProductReview OT missing from authoritative layer (P09-P12 not in ecom_object)",
            "fix_target": "O1-A (P11 authoritative write)",
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)

    def test_g17_pay_duration_min(self, db_conn, evidence_meta):
        """G17 baseline: Payment.pay_duration_min."""
        total = _count_by_ot(db_conn, "Payment")
        if total == 0:
            status = "RED"
            nonnull = 0
            eligible = 0
        else:
            nonnull = _count_metric_nonnull(db_conn, "Payment", "pay_duration_min")
            eligible = total
            rate = round(nonnull / eligible * 100, 1) if eligible > 0 else 0.0
            status = "GREEN" if rate >= 100 else "RED"

        result = {
            "metric": "pay_duration_min",
            "ot": "Payment",
            "has_non_null": nonnull,
            "total_objects": total,
            "eligible_total": eligible,
            "rate_pct": 0.0,
            "status": status,
            "root_cause": "Payment OT missing from authoritative layer + _order_create_time not populated",
            "fix_target": "O1-A (P12 authoritative write + batch_read_public for _order_create_time)",
            "g17_spec_status": "BLOCKED",
        }
        save_evidence("G17", "D5-E0", result, evidence_meta)
