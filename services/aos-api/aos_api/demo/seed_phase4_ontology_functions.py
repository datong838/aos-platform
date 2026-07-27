"""Phase 4 seed · Ontology Functions — 10 function + 20 测试用例 (合计 30)."""
from __future__ import annotations

from aos_api.ontology_function_engine import get_function_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_functions")


_FUNCTIONS_SPEC: list[dict] = [
    {
        "name": "compute_discount",
        "display_name": "Compute Discount",
        "description": "根据订单金额和客户等级计算折扣",
        "body": "return amount * (0.1 if tier == 'Gold' else 0.05)",
        "params": [
            {"name": "amount", "datatype": "double", "description": "订单金额"},
            {"name": "tier", "datatype": "string", "description": "客户等级"},
        ],
        "return_type": "double",
        "category": "transform",
    },
    {
        "name": "format_full_name",
        "display_name": "Format Full Name",
        "description": "拼接姓和名",
        "body": "return first + ' ' + last",
        "params": [
            {"name": "first", "datatype": "string"},
            {"name": "last", "datatype": "string"},
        ],
        "return_type": "string",
        "category": "transform",
    },
    {
        "name": "is_high_value_customer",
        "display_name": "Is High Value Customer",
        "description": "判断是否高价值客户",
        "body": "return revenue > 1000000 and tier in ['Gold', 'Platinum']",
        "params": [
            {"name": "revenue", "datatype": "double"},
            {"name": "tier", "datatype": "string"},
        ],
        "return_type": "boolean",
        "category": "predicate",
    },
    {
        "name": "sum_order_amounts",
        "display_name": "Sum Order Amounts",
        "description": "聚合订单总金额",
        "body": "return sum(orders)",
        "params": [{"name": "orders", "datatype": "json"}],
        "return_type": "double",
        "category": "aggregate",
    },
    {
        "name": "compute_tax",
        "display_name": "Compute Tax",
        "description": "计算税额",
        "body": "return amount * 0.08",
        "params": [{"name": "amount", "datatype": "double"}],
        "return_type": "double",
        "category": "transform",
    },
    {
        "name": "days_between",
        "display_name": "Days Between",
        "description": "计算两个日期之间的天数",
        "body": "return (end - start).days",
        "params": [{"name": "start", "datatype": "date"}, {"name": "end", "datatype": "date"}],
        "return_type": "int",
        "category": "transform",
    },
    {
        "name": "is_shipped",
        "display_name": "Is Shipped",
        "description": "判断订单是否已发货",
        "body": "return status in ['shipped', 'delivered']",
        "params": [{"name": "status", "datatype": "string"}],
        "return_type": "boolean",
        "category": "predicate",
    },
    {
        "name": "avg_rating",
        "display_name": "Average Rating",
        "description": "计算平均评级",
        "body": "return sum(ratings) / len(ratings)",
        "params": [{"name": "ratings", "datatype": "json"}],
        "return_type": "double",
        "category": "aggregate",
    },
    {
        "name": "mask_email",
        "display_name": "Mask Email",
        "description": "脱敏邮箱",
        "body": "return email.split('@')[0][:2] + '***@' + email.split('@')[1]",
        "params": [{"name": "email", "datatype": "string"}],
        "return_type": "string",
        "category": "transform",
    },
    {
        "name": "classify_tier",
        "display_name": "Classify Tier",
        "description": "根据收入自动分类客户等级",
        "body": "return 'Platinum' if r > 5e6 else 'Gold' if r > 1e6 else 'Silver'",
        "params": [{"name": "r", "datatype": "double"}],
        "return_type": "string",
        "category": "custom",
    },
]


def seed_phase4_ontology_functions() -> int:
    """Seed 10 functions + 20 tests. Returns total count."""
    eng = get_function_engine()
    total = 0
    fn_ids: list[str] = []
    for spec in _FUNCTIONS_SPEC:
        fn = eng.create_function(**spec)
        fn_ids.append(fn.id)
        total += 1

    # 为前 10 个 function 添加 2 个测试 = 20
    for i, fid in enumerate(fn_ids):
        eng.add_test(
            fid,
            name=f"test_case_{i}_1",
            inputs={"x": 100 + i},
            expected=None,
        )
        eng.add_test(
            fid,
            name=f"test_case_{i}_2",
            inputs={"x": 200 + i},
            expected=None,
        )
        total += 2

    log.info("seed_phase4_ontology_functions_done functions=%s tests=%s total=%s", len(fn_ids), total - len(fn_ids), total)
    return total
