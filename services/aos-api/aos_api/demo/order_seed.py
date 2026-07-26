"""订单测试数据种子：Order ObjectType + 20 条订单 + OrderItem + LinkType。

从原 ``aos_api/order_seed.py`` 搬迁而来。仅在 ``demo.seed_test_org()`` 时调用。
"""
from __future__ import annotations

import json

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.order_seed")

_ORDER_PROPS = json.dumps(
    [
        {"name": "order_no", "type": "string"},
        {"name": "customer_id", "type": "string"},
        {"name": "customer_name", "type": "string"},
        {"name": "order_date", "type": "string"},
        {"name": "total_amount", "type": "number"},
        {"name": "status", "type": "string"},
        {"name": "shipping_address", "type": "string"},
        {"name": "items", "type": "json"},
        {"name": "tracking_no", "type": "string"},
        {"name": "remark", "type": "string"},
    ]
)

_ORDER_ITEM_PROPS = json.dumps(
    [
        {"name": "order_id", "type": "string"},
        {"name": "product_name", "type": "string"},
        {"name": "quantity", "type": "number"},
        {"name": "unit_price", "type": "number"},
        {"name": "subtotal", "type": "number"},
    ]
)

_SAMPLE_ORDERS = [
    ("ord-001", "ORD-20251", "CUST-8847", "张伟", "2026-07-22", 1299, "shipped", "北京市朝阳区建国路88号", [{"product": "无线蓝牙耳机", "qty": 1, "price": 1299}], "SF1234567890", ""),
    ("ord-002", "ORD-20252", "CUST-2391", "李娜", "2026-07-22", 459, "delivered", "上海市浦东新区世纪大道100号", [{"product": "便携充电宝", "qty": 1, "price": 459}], "YT9876543210", ""),
    ("ord-003", "ORD-20253", "CUST-7102", "王芳", "2026-07-22", 2880, "paid", "广州市天河区体育西路191号", [{"product": "智能手表", "qty": 2, "price": 1440}], "", ""),
    ("ord-004", "ORD-20254", "CUST-5538", "刘洋", "2026-07-21", 76, "delivered", "深圳市南山区科技园南区", [{"product": "手机壳", "qty": 2, "price": 38}], "", ""),
    ("ord-005", "ORD-20255", "CUST-9981", "陈静", "2026-07-21", 1549, "shipped", "杭州市西湖区文三路478号", [{"product": "机械键盘", "qty": 1, "price": 1549}], "JD5556667778", ""),
    ("ord-006", "ORD-20256", "CUST-3344", "杨光", "2026-07-20", 5880, "paid", "成都市武侯区天府大道北段1700号", [{"product": "游戏笔记本", "qty": 1, "price": 5880}], "", "加急"),
    ("ord-007", "ORD-20257", "CUST-6655", "赵雪", "2026-07-20", 329, "pending", "武汉市江汉区解放大道690号", [{"product": "保温杯", "qty": 1, "price": 329}], "", ""),
    ("ord-008", "ORD-20258", "CUST-1122", "黄磊", "2026-07-19", 2199, "shipped", "南京市鼓楼区中山北路12号", [{"product": "扫地机器人", "qty": 1, "price": 2199}], "ZTO1112223334", ""),
    ("ord-009", "ORD-20259", "CUST-7788", "周婷", "2026-07-19", 899, "delivered", "西安市雁塔区高新路25号", [{"product": "电动牙刷", "qty": 1, "price": 899}], "", ""),
    ("ord-010", "ORD-20260", "CUST-4455", "吴昊", "2026-07-18", 4299, "paid", "重庆市渝中区解放碑步行街", [{"product": "4K显示器", "qty": 1, "price": 4299}], "", ""),
    ("ord-011", "ORD-20261", "CUST-2266", "郑爽", "2026-07-18", 159, "cancelled", "苏州市工业园区现代大道188号", [{"product": "USB-C数据线", "qty": 3, "price": 53}], "", "用户取消"),
    ("ord-012", "ORD-20262", "CUST-8899", "孙强", "2026-07-17", 3680, "delivered", "天津市和平区南京路189号", [{"product": "空气净化器", "qty": 1, "price": 3680}], "", ""),
    ("ord-013", "ORD-20263", "CUST-3300", "马丽", "2026-07-17", 649, "pending", "长沙市岳麓区麓山南路932号", [{"product": "智能台灯", "qty": 1, "price": 649}], "", ""),
    ("ord-014", "ORD-20264", "CUST-5511", "朱亚", "2026-07-16", 1799, "refunded", "郑州市金水区花园路100号", [{"product": "咖啡机", "qty": 1, "price": 1799}], "", "商品损坏退款"),
    ("ord-015", "ORD-20265", "CUST-9933", "胡敏", "2026-07-16", 239, "delivered", "青岛市市南区香港中路76号", [{"product": "蓝牙音箱", "qty": 1, "price": 239}], "", ""),
    ("ord-016", "ORD-20266", "CUST-7744", "林峰", "2026-07-15", 9599, "shipped", "大连市中山区人民路15号", [{"product": "旗舰手机", "qty": 1, "price": 9599}], "SF8889990001", ""),
    ("ord-017", "ORD-20267", "CUST-2255", "何琳", "2026-07-15", 488, "paid", "厦门市思明区湖滨北路95号", [{"product": "体重秤", "qty": 1, "price": 488}], "", ""),
    ("ord-018", "ORD-20268", "CUST-6677", "高远", "2026-07-14", 3199, "delivered", "沈阳市和平区中华路65号", [{"product": "投影仪", "qty": 1, "price": 3199}], "", ""),
    ("ord-019", "ORD-20269", "CUST-1100", "罗欣", "2026-07-14", 129, "pending", "哈尔滨市南岗区西大直街92号", [{"product": "鼠标垫", "qty": 1, "price": 129}], "", ""),
    ("ord-020", "ORD-20270", "CUST-4422", "宋杰", "2026-07-13", 2799, "refunded", "长春市朝阳区同志街55号", [{"product": "吸尘器", "qty": 1, "price": 2799}], "", "七天无理由退款"),
]


def _build_order_props(record: tuple) -> str:
    (
        _oid,
        order_no,
        customer_id,
        customer_name,
        order_date,
        total_amount,
        status,
        shipping_address,
        items,
        tracking_no,
        remark,
    ) = record
    return json.dumps(
        {
            "order_no": order_no,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "order_date": order_date,
            "total_amount": total_amount,
            "status": status,
            "shipping_address": shipping_address,
            "items": items,
            "tracking_no": tracking_no,
            "remark": remark,
        },
        ensure_ascii=False,
    )


def seed_orders() -> int:
    """幂等灌入 Order + OrderItem ObjectType + 20 条样例订单 + LinkType。

    Returns:
        样例订单数（20）。
    """
    from aos_api.db import connect

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            ("Order", "订单", "Phase C+ 电商订单管理", True, _ORDER_PROPS),
        )
        conn.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            ("OrderItem", "订单明细", "Phase C+ 订单明细子表", True, _ORDER_ITEM_PROPS),
        )

        count_row = conn.execute(
            "SELECT COUNT(*) AS c FROM obj_instance WHERE object_type = 'Order'"
        ).fetchone()
        if count_row and int(count_row["c"]) == 0:
            for record in _SAMPLE_ORDERS:
                oid = record[0]
                props = _build_order_props(record)
                conn.execute(
                    """
                    INSERT INTO obj_instance (object_type, object_id, props)
                    VALUES ('Order', %s, %s::jsonb)
                    """,
                    (oid, props),
                )
            log.info("order_seed: inserted %d sample orders", len(_SAMPLE_ORDERS))

        conn.execute(
            """
            INSERT INTO meta_link_type
              (id, name, src_type, dst_type, rel, cardinality, published, description)
            VALUES
              ('lt-order-item', '订单明细', 'Order', 'OrderItem', 'has_item', 'ONE_TO_MANY', TRUE, '订单包含多个明细项')
            ON CONFLICT (id) DO NOTHING
            """
        )
        conn.commit()

    log.info("seed_orders_done samples=%s", len(_SAMPLE_ORDERS))
    return len(_SAMPLE_ORDERS)
