"""Phase 4 seed · Ontology Objects — 80 个对象实例 (每类型 12-15)."""
from __future__ import annotations

from aos_api.ontology_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_objects")


def _customers() -> list[dict]:
    regions = ["North", "South", "East", "West", "Central"]
    tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    industries = ["Retail", "Manufacturing", "Finance", "Healthcare", "Tech"]
    items = []
    for i in range(1, 16):  # 15
        items.append(
            {
                "name": f"Customer-{i:03d}",
                "props": {
                    "customer_id": f"C{i:04d}",
                    "name": f"Acme Corp {i}",
                    "email": f"contact{i}@acme.com",
                    "phone": f"+1-555-01{i:02d}",
                    "region": regions[i % len(regions)],
                    "tier": tiers[i % len(tiers)],
                    "annual_revenue": 1_000_000 * i + 12345.67,
                    "employee_count": 50 * i + 10,
                    "industry": industries[i % len(industries)],
                    "status": "active" if i % 3 else "inactive",
                    "created_date": f"2024-{(i % 12) + 1:02d}-15",
                    "last_activity": f"2025-0{(i % 9) + 1}-12 10:30:00",
                },
            }
        )
    return items


def _orders() -> list[dict]:
    statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    channels = ["online", "store", "phone", "partner"]
    items = []
    for i in range(1, 16):  # 15
        items.append(
            {
                "name": f"Order-{i:04d}",
                "props": {
                    "order_id": f"ORD-{i:05d}",
                    "customer_id": f"C{(i % 13) + 1:04d}",
                    "order_date": f"2025-0{(i % 9) + 1}-10",
                    "ship_date": f"2025-0{(i % 9) + 1}-15" if i % 4 else "",
                    "total_amount": 999.99 * i + 0.5,
                    "currency": "USD",
                    "status": statuses[i % len(statuses)],
                    "channel": channels[i % len(channels)],
                    "discount": 0.05 * (i % 5),
                    "payment_method": "credit_card" if i % 2 else "wire",
                },
            }
        )
    return items


def _products() -> list[dict]:
    cats = ["Electronics", "Apparel", "Home", "Sports", "Books"]
    items = []
    for i in range(1, 16):  # 15
        items.append(
            {
                "name": f"Product-{i:03d}",
                "props": {
                    "product_id": f"P{i:04d}",
                    "sku": f"SKU-{i:05d}",
                    "name": f"Widget Type {i}",
                    "category": cats[i % len(cats)],
                    "price": 19.99 * i + 0.99,
                    "cost": 9.5 * i,
                    "weight": 0.5 * i + 0.1,
                    "in_stock": i % 2 == 0,
                    "description": f"High-quality widget #{i}",
                    "launch_date": f"2023-{(i % 12) + 1:02d}-01",
                    "supplier_id": f"S{(i % 9) + 1:03d}",
                },
            }
        )
    return items


def _suppliers() -> list[dict]:
    countries = ["USA", "China", "Germany", "Japan", "Brazil"]
    items = []
    for i in range(1, 13):  # 12
        items.append(
            {
                "name": f"Supplier-{i:03d}",
                "props": {
                    "supplier_id": f"S{i:03d}",
                    "name": f"Global Supplies {i}",
                    "country": countries[i % len(countries)],
                    "contact_email": f"sales{i}@supplier.com",
                    "contact_phone": f"+1-800-{i:03d}",
                    "rating": 3.5 + (i % 3) * 0.5,
                    "lead_time_days": 5 + (i % 10),
                    "payment_terms": "Net 30" if i % 2 else "Net 60",
                    "active": True,
                },
            }
        )
    return items


def _shipments() -> list[dict]:
    statuses = ["pending", "in_transit", "delivered", "returned"]
    carriers = ["FedEx", "UPS", "DHL", "SF Express"]
    items = []
    for i in range(1, 15):  # 14
        items.append(
            {
                "name": f"Shipment-{i:04d}",
                "props": {
                    "shipment_id": f"SHP-{i:05d}",
                    "order_id": f"ORD-{(i % 13) + 1:05d}",
                    "origin": "Warehouse-A",
                    "destination": f"City-{i}",
                    "carrier": carriers[i % len(carriers)],
                    "tracking_no": f"TRK{i:010d}",
                    "weight_kg": 1.2 * i + 0.3,
                    "shipped_at": f"2025-0{(i % 9) + 1}-12 09:00:00",
                    "delivered_at": f"2025-0{(i % 9) + 1}-15 14:00:00" if i % 3 == 0 else "",
                    "status": statuses[i % len(statuses)],
                    "cost": 15.0 * i + 2.5,
                },
            }
        )
    return items


def _invoices() -> list[dict]:
    statuses = ["draft", "sent", "paid", "overdue"]
    items = []
    for i in range(1, 17):  # 16
        items.append(
            {
                "name": f"Invoice-{i:04d}",
                "props": {
                    "invoice_id": f"INV-{i:05d}",
                    "order_id": f"ORD-{(i % 13) + 1:05d}",
                    "customer_id": f"C{(i % 13) + 1:04d}",
                    "issue_date": f"2025-0{(i % 9) + 1}-05",
                    "due_date": f"2025-{(i % 9) + 1:02d}-05",
                    "amount": 500.0 * i + 12.34,
                    "tax": 50.0 * i + 1.23,
                    "status": statuses[i % len(statuses)],
                    "paid_date": f"2025-0{(i % 9) + 1}-20" if i % 3 == 0 else "",
                },
            }
        )
    return items


def seed_phase4_ontology_objects() -> int:
    """Seed 80 object instances. Returns count."""
    eng = get_engine()
    types_by_name = {ot.name: ot for ot in eng.list_object_types(page=1, page_size=200)[0]}
    total = 0
    loaders = [
        ("customer", _customers()),
        ("order", _orders()),
        ("product", _products()),
        ("supplier", _suppliers()),
        ("shipment", _shipments()),
        ("invoice", _invoices()),
    ]
    for tname, items in loaders:
        ot = types_by_name.get(tname)
        if not ot:
            continue
        for it in items:
            eng.create_object(ot.id, name=it["name"], properties=it["props"])
            total += 1
    log.info("seed_phase4_ontology_objects_done total=%s", total)
    return total
