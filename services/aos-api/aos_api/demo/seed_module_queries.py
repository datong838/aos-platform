"""Seed module queries — Phase 1 Workshop backend.

20 query functions: 2-3 per module.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import stable_module_pk
from aos_api.module_queries import ensure_schema

log = get_logger("aos-api.demo.seed_module_queries")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_QUERIES = {
    "dev-module-order": [
        {"id": "q-order-list", "name": "订单列表查询", "queryType": "sql", "source": "Order", "statement": "SELECT * FROM orders WHERE status = :status ORDER BY created_at DESC", "params": [{"key": "status", "type": "string", "default": "all"}]},
        {"id": "q-order-stats", "name": "订单统计", "queryType": "sql", "source": "Order", "statement": "SELECT status, COUNT(*) as cnt, SUM(total_amount) as total FROM orders GROUP BY status", "params": []},
        {"id": "q-order-trend", "name": "订单趋势", "queryType": "sql", "source": "Order", "statement": "SELECT DATE(order_date) as d, COUNT(*) as c FROM orders WHERE order_date > NOW() - INTERVAL '7 days' GROUP BY d", "params": []},
    ],
    "dev-module-risk": [
        {"id": "q-risk-events", "name": "风险事件列表", "queryType": "sql", "source": "RiskEvent", "statement": "SELECT * FROM risk_events WHERE severity >= :severity ORDER BY created_at DESC", "params": [{"key": "severity", "type": "number", "default": 1}]},
        {"id": "q-risk-summary", "name": "风险汇总", "queryType": "sql", "source": "RiskEvent", "statement": "SELECT risk_type, COUNT(*) as cnt FROM risk_events GROUP BY risk_type", "params": []},
    ],
    "dev-module-customer": [
        {"id": "q-customer-list", "name": "客户列表", "queryType": "sql", "source": "Customer", "statement": "SELECT * FROM customers ORDER BY created_at DESC", "params": []},
        {"id": "q-customer-segments", "name": "客户分群", "queryType": "sql", "source": "Customer", "statement": "SELECT segment, COUNT(*) as cnt FROM customers GROUP BY segment", "params": []},
        {"id": "q-customer-detail", "name": "客户详情", "queryType": "sql", "source": "Customer", "statement": "SELECT * FROM customers WHERE customer_id = :customerId", "params": [{"key": "customerId", "type": "string"}]},
    ],
    "dev-module-asset": [
        {"id": "q-asset-list", "name": "资产列表", "queryType": "sql", "source": "Asset", "statement": "SELECT * FROM assets ORDER BY name", "params": []},
        {"id": "q-asset-depreciation", "name": "折旧统计", "queryType": "sql", "source": "Asset", "statement": "SELECT category, SUM(current_value) as val FROM assets GROUP BY category", "params": []},
    ],
    "dev-module-analysis": [
        {"id": "q-analysis-funnel", "name": "漏斗分析", "queryType": "sql", "source": "Analysis", "statement": "SELECT stage, COUNT(*) as cnt FROM user_events GROUP BY stage ORDER BY stage", "params": []},
        {"id": "q-analysis-retention", "name": "留存分析", "queryType": "sql", "source": "Analysis", "statement": "SELECT cohort_day, retention_rate FROM retention_curve", "params": []},
        {"id": "q-analysis-cohort", "name": "同群分析", "queryType": "sql", "source": "Analysis", "statement": "SELECT cohort, day_n, active_users FROM cohort_matrix", "params": []},
    ],
    "dev-module-workorder": [
        {"id": "q-workorder-list", "name": "工单列表", "queryType": "sql", "source": "WorkOrder", "statement": "SELECT * FROM workorders WHERE status = :status", "params": [{"key": "status", "type": "string", "default": "open"}]},
        {"id": "q-workorder-stats", "name": "工单统计", "queryType": "sql", "source": "WorkOrder", "statement": "SELECT priority, COUNT(*) as cnt FROM workorders GROUP BY priority", "params": []},
    ],
    "dev-module-inventory": [
        {"id": "q-inventory-list", "name": "库存列表", "queryType": "sql", "source": "Inventory", "statement": "SELECT * FROM inventory_items ORDER BY name", "params": []},
        {"id": "q-inventory-low", "name": "低库存预警", "queryType": "sql", "source": "Inventory", "statement": "SELECT * FROM inventory_items WHERE quantity < threshold", "params": []},
        {"id": "q-inventory-movement", "name": "出入库记录", "queryType": "sql", "source": "Inventory", "statement": "SELECT * FROM inventory_movements ORDER BY created_at DESC LIMIT 100", "params": []},
    ],
    "dev-module-finance": [
        {"id": "q-finance-ar", "name": "应收账款", "queryType": "sql", "source": "Finance", "statement": "SELECT * FROM accounts_receivable WHERE status = 'open'", "params": []},
        {"id": "q-finance-summary", "name": "财务汇总", "queryType": "sql", "source": "Finance", "statement": "SELECT account_type, SUM(amount) as total FROM ledger_entries GROUP BY account_type", "params": []},
    ],
    "dev-module-marketing": [
        {"id": "q-marketing-campaigns", "name": "活动列表", "queryType": "sql", "source": "Campaign", "statement": "SELECT * FROM campaigns ORDER BY start_date DESC", "params": []},
        {"id": "q-marketing-roi", "name": "ROI 分析", "queryType": "sql", "source": "Campaign", "statement": "SELECT campaign_id, revenue / cost as roi FROM campaign_metrics", "params": []},
    ],
}


def seed_module_queries() -> int:
    """Idempotently seed 20 query functions. Returns count."""
    ensure_schema()
    count = 0
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM module_query
             WHERE module_id LIKE 'dev-module-%%' AND org_id=%s
            """,
            (_DEFAULT_ORG,),
        )

        for module_id, queries in _QUERIES.items():
            for q in queries:
                conn.execute(
                    """
                    INSERT INTO module_query (
                        id, module_id, name, description, query_type, source,
                        statement, params, enabled, org_id, project_id, module_pk
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    ON CONFLICT (org_id, project_id, id) DO UPDATE SET
                        name=EXCLUDED.name, statement=EXCLUDED.statement,
                        params=EXCLUDED.params, query_type=EXCLUDED.query_type
                    """,
                    (
                        q["id"],
                        module_id,
                        q["name"],
                        q.get("description", ""),
                        q.get("queryType", "sql"),
                        q.get("source", ""),
                        q.get("statement", ""),
                        json.dumps(q.get("params", [])),
                        True,
                        _DEFAULT_ORG,
                        _DEFAULT_PROJECT,
                        stable_module_pk(_DEFAULT_ORG, _DEFAULT_PROJECT, module_id),
                    ),
                )
                count += 1

        conn.commit()
    log.info("seed_module_queries_done count=%s", count)
    return count
