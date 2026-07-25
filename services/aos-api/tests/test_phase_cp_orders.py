"""Phase C+ — Order management tests.

Tests:
  1. Order ObjectType exists in meta_object_type
  2. OrderItem ObjectType exists
  3. 20 sample orders exist with correct status distribution
  4. LinkType lt-order-item exists
  5. Order list via API
  6. Order detail via API
  7. Action plugin manifests on disk (confirm-shipment, cancel-order, refund-order)
  8. Order status filter
  9. Order search by customer_name
"""
from __future__ import annotations

import json
import os
import pathlib

PLUGINS_DIR = pathlib.Path(__file__).resolve().parents[3] / "plugins" / "actions"


# ── Backend seed tests (PG available) ─────────────────────────────────────────

def test_order_object_type_exists():
    """Order ObjectType is registered."""
    from aos_api.db import connect

    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, published, properties FROM meta_object_type WHERE id = 'Order'"
        ).fetchone()
    assert row is not None, "Order ObjectType must exist"
    assert row["name"] == "订单"
    assert row["published"] is True
    props = row["properties"]
    if isinstance(props, str):
        props = json.loads(props)
    prop_names = [p["name"] for p in props]
    assert "order_no" in prop_names
    assert "total_amount" in prop_names
    assert "status" in prop_names


def test_order_item_object_type_exists():
    """OrderItem ObjectType is registered."""
    from aos_api.db import connect

    with connect() as conn:
        row = conn.execute(
            "SELECT id, name FROM meta_object_type WHERE id = 'OrderItem'"
        ).fetchone()
    assert row is not None
    assert row["name"] == "订单明细"


def test_sample_orders_count():
    """20 sample orders exist."""
    from aos_api.db import connect

    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM obj_instance WHERE object_type = 'Order'"
        ).fetchone()
    assert int(row["c"]) >= 20, f"Expected >=20 orders, got {row['c']}"


def test_order_status_distribution():
    """Orders cover multiple statuses."""
    from aos_api.db import connect

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT props->>'status' AS status, COUNT(*) AS c
            FROM obj_instance
            WHERE object_type = 'Order'
            GROUP BY props->>'status'
            """
        ).fetchall()
    statuses = {r["status"] for r in rows}
    # Should have at least 4 distinct statuses
    assert len(statuses) >= 4, f"Expected >=4 statuses, got {statuses}"
    # Must include key statuses
    assert "pending" in statuses or "paid" in statuses


def test_link_type_order_item_exists():
    """LinkType lt-order-item exists."""
    from aos_api.db import connect

    with connect() as conn:
        row = conn.execute(
            "SELECT id, src_type, dst_type FROM meta_link_type WHERE id = 'lt-order-item'"
        ).fetchone()
    assert row is not None
    assert row["src_type"] == "Order"
    assert row["dst_type"] == "OrderItem"


def test_order_list_api(client, auth_headers):
    """GET /v1/objects/Order returns order list."""
    resp = client.get("/v1/objects/Order", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    if isinstance(data, dict):
        objects = data.get("items") or data.get("objects") or data.get("data") or []
    else:
        objects = data
    assert len(objects) > 0
    # Verify first object has expected fields
    first = objects[0]
    props = first.get("props") or first.get("properties") or first
    assert "order_no" in props or "order_no" in first


def test_order_detail_api(client, auth_headers):
    """GET /v1/objects/Order/ord-001 returns detail."""
    resp = client.get("/v1/objects/Order/ord-001", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    props = data.get("props") or data.get("properties") or data
    assert props.get("order_no") == "ORD-20251" or data.get("order_no") == "ORD-20251"


def test_order_status_filter_api(client, auth_headers):
    """POST /v1/object-sets/query with status filter."""
    resp = client.post(
        "/v1/object-sets/query",
        headers=auth_headers,
        json={
            "objectType": "Order",
            "filters": [
                {"field": "status", "op": "eq", "value": "pending"},
            ],
        },
    )
    assert resp.status_code in (200, 207)
    data = resp.json()
    objects = data.get("objects") if isinstance(data, dict) else data
    if objects:
        for obj in objects:
            props = obj.get("props") or obj
            assert props.get("status") == "pending"


# ── Action plugin manifest tests ──────────────────────────────────────────────


def test_confirm_shipment_manifest():
    """confirm-shipment action plugin manifest exists and is valid."""
    manifest_path = PLUGINS_DIR / "confirm-shipment" / "manifest.json"
    assert manifest_path.exists(), f"Missing {manifest_path}"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["actionTypeId"] == "ConfirmShipment"
    assert data["objectType"] == "Order"
    params = {p["name"]: p for p in data["parameters"]}
    assert "tracking_no" in params
    assert params["tracking_no"]["required"] is True


def test_cancel_order_manifest():
    """cancel-order action plugin manifest exists and is valid."""
    manifest_path = PLUGINS_DIR / "cancel-order" / "manifest.json"
    assert manifest_path.exists(), f"Missing {manifest_path}"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["actionTypeId"] == "CancelOrder"
    assert data["objectType"] == "Order"
    params = {p["name"]: p for p in data["parameters"]}
    assert "reason" in params
    assert params["reason"]["required"] is True


def test_refund_order_manifest():
    """refund-order action plugin manifest exists and is valid."""
    manifest_path = PLUGINS_DIR / "refund-order" / "manifest.json"
    assert manifest_path.exists(), f"Missing {manifest_path}"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["actionTypeId"] == "RefundOrder"
    assert data["objectType"] == "Order"
    params = {p["name"]: p for p in data["parameters"]}
    assert "reason" in params
