"""Seed module interfaces — Phase 1 Workshop backend.

9 interface definitions, one per module.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_interfaces import ensure_schema

log = get_logger("aos-api.demo.seed_module_interfaces")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_INTERFACES = {
    "dev-module-order": {"name": "OrderAPI", "entryParams": [{"key": "orderId", "type": "string", "required": True}], "expose": {"endpoint": "/api/orders", "method": "GET"}},
    "dev-module-risk": {"name": "RiskAPI", "entryParams": [{"key": "severity", "type": "number"}], "expose": {"endpoint": "/api/risks", "method": "GET"}},
    "dev-module-customer": {"name": "CustomerAPI", "entryParams": [{"key": "customerId", "type": "string", "required": True}], "expose": {"endpoint": "/api/customers", "method": "GET"}},
    "dev-module-asset": {"name": "AssetAPI", "entryParams": [{"key": "category", "type": "string"}], "expose": {"endpoint": "/api/assets", "method": "GET"}},
    "dev-module-analysis": {"name": "AnalysisAPI", "entryParams": [{"key": "metric", "type": "string"}], "expose": {"endpoint": "/api/analysis", "method": "POST"}},
    "dev-module-workorder": {"name": "WorkOrderAPI", "entryParams": [{"key": "workOrderId", "type": "string", "required": True}], "expose": {"endpoint": "/api/workorders", "method": "GET"}},
    "dev-module-inventory": {"name": "InventoryAPI", "entryParams": [{"key": "sku", "type": "string"}], "expose": {"endpoint": "/api/inventory", "method": "GET"}},
    "dev-module-finance": {"name": "FinanceAPI", "entryParams": [{"key": "accountId", "type": "string"}], "expose": {"endpoint": "/api/finance", "method": "GET"}},
    "dev-module-marketing": {"name": "MarketingAPI", "entryParams": [{"key": "campaignId", "type": "string"}], "expose": {"endpoint": "/api/campaigns", "method": "GET"}},
}


def seed_module_interfaces() -> int:
    """Idempotently seed 9 interface definitions. Returns count."""
    ensure_schema()
    count = 0
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM module_interface
             WHERE module_id LIKE 'dev-module-%%' AND org_id=%s
            """,
            (_DEFAULT_ORG,),
        )

        for module_id, iface in _INTERFACES.items():
            conn.execute(
                """
                INSERT INTO module_interface (
                    module_id, name, description, entry_params, expose,
                    version, org_id, project_id
                ) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                ON CONFLICT (module_id) DO UPDATE SET
                    name=EXCLUDED.name, entry_params=EXCLUDED.entry_params,
                    expose=EXCLUDED.expose, version=EXCLUDED.version,
                    updated_at=NOW()
                """,
                (
                    module_id,
                    iface["name"],
                    f"{iface['name']} 接口定义",
                    json.dumps(iface["entryParams"]),
                    json.dumps(iface["expose"]),
                    "1.0.0",
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
            count += 1

        conn.commit()
    log.info("seed_module_interfaces_done count=%s", count)
    return count
