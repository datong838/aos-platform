"""WorkOrder 测试数据种子：ObjectType + 样例工单 + 关联 + wiki + funnel。

从原 ``db.py`` 的 ``seed_if_empty`` 中 WorkOrder 部分 +
``repair_demo_workorders`` + ``ensure_field_marking_seed`` + ``ensure_inherit_openfga_seed``
搬迁而来。

注意：``WorkOrder`` ObjectType 在系统启动时由 ``ensure_system_meta`` 兜底创建（避免
ObjectType 缺失导致前端 500），但**样例工单数据**只在 ``seed_test_org`` 时灌入。
"""
from __future__ import annotations

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.workorder_seed")

_WORKORDER_PROPS = (
    "["
    '{"name":"title","type":"string"},'
    '{"name":"status","type":"string"},'
    '{"name":"site","type":"string"},'
    '{"name":"priority","type":"string"},'
    '{"name":"internalCost","type":"number","requiredMarkings":["secret"]}'
    "]"
)

_WORKORDER_SAMPLES = [
    (
        "WorkOrder",
        "wo-1001",
        '{"title":"机房巡检-A区","status":"open","site":"DC-East","priority":"P1","internalCost":1280}',
    ),
    (
        "WorkOrder",
        "wo-1002",
        '{"title":"链路告警复核","status":"in_progress","site":"DC-West","priority":"P0","internalCost":640}',
    ),
    (
        "WorkOrder",
        "wo-1003",
        '{"title":"备件更换","status":"open","site":"DC-East","priority":"P2","internalCost":320}',
    ),
    # 36 §7 · MySQL 供数样例（防 utf8 双重编码乱码残留）
    (
        "WorkOrder",
        "mysql-wo-001",
        '{"title":"MySQL供数-巡检单","status":"open","site":"DC-East","priority":"P1"}',
    ),
    (
        "WorkOrder",
        "mysql-wo-002",
        '{"title":"MySQL供数-备件","status":"in_progress","site":"DC-West","priority":"P0"}',
    ),
]


def _ensure_workorder_object_type(conn) -> None:
    """确保 WorkOrder ObjectType 存在（含 internalCost requiredMarkings）。"""
    conn.execute(
        """
        INSERT INTO meta_object_type (id, name, description, published, properties)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (id) DO UPDATE SET properties = EXCLUDED.properties
        """,
        (
            "WorkOrder",
            "工单",
            "Wave-2 seed Object Type",
            True,
            _WORKORDER_PROPS,
        ),
    )


def _ensure_site_object_type(conn) -> None:
    """Site ObjectType（marking 继承父）+ 站点实例。"""
    conn.execute(
        """
        INSERT INTO meta_object_type (id, name, description, published, properties, required_markings)
        VALUES (%s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        ("Site", "站点", "Marking inheritance parent (scheme 55)", True),
    )
    conn.execute(
        """
        INSERT INTO obj_instance (object_type, object_id, props)
        VALUES (
          'Site', 'site-east',
          '{"name":"DC-East","_requiredMarkings":["restricted"]}'::jsonb
        )
        ON CONFLICT (object_type, object_id)
        DO UPDATE SET props = EXCLUDED.props
        """
    )


def _ensure_sample_workorders(conn, *, repair: bool) -> int:
    """写入 5 条 WorkOrder 样例（repair=True 时强制刷新 props）。"""
    if repair:
        for t, i, p in _WORKORDER_SAMPLES:
            conn.execute(
                """
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                """,
                (t, i, p),
            )
    else:
        for t, i, p in _WORKORDER_SAMPLES:
            conn.execute(
                """
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT DO NOTHING
                """,
                (t, i, p),
            )
    return len(_WORKORDER_SAMPLES)


def _ensure_graph_edges(conn) -> None:
    """WorkOrder 之间关联 + wo-1003 继承 site-east 标记。"""
    conn.execute(
        """
        INSERT INTO graph_edge (src_type, src_id, rel, dst_type, dst_id)
        VALUES ('WorkOrder','wo-1001','related_to','WorkOrder','wo-1003')
        ON CONFLICT DO NOTHING
        """
    )
    conn.execute(
        """
        INSERT INTO graph_edge (src_type, src_id, rel, dst_type, dst_id)
        VALUES ('WorkOrder','wo-1003','inherits_markings_from','Site','site-east')
        ON CONFLICT DO NOTHING
        """
    )


def _ensure_fga_demo(conn) -> None:
    """OpenFGA demo tuples + wo-fga-demo 样例。"""
    conn.execute(
        """
        INSERT INTO obj_instance (object_type, object_id, props)
        VALUES (
          'WorkOrder', 'wo-fga-demo',
          '{"title":"OpenFGA demo","status":"open","site":"DC-East","priority":"P2"}'::jsonb
        )
        ON CONFLICT (object_type, object_id) DO NOTHING
        """
    )
    conn.execute(
        """
        INSERT INTO authz_tuple (user_key, relation, object_key)
        VALUES
          ('user:secret-user', 'viewer', 'object:WorkOrder:wo-fga-demo'),
          ('user:secret-user', 'member', 'organization:dev-org'),
          ('organization:dev-org', 'parent', 'project:dev-project'),
          ('user:secret-user', 'bearer', 'marking:restricted'),
          ('user:bearer-only', 'bearer', 'marking:restricted'),
          ('user:field-bearer', 'bearer', 'marking:secret')
        ON CONFLICT DO NOTHING
        """
    )


def _ensure_wiki_and_funnel(conn) -> None:
    """WorkOrder wiki + funnel_status。"""
    conn.execute(
        """
        INSERT INTO wiki_page (object_type, object_id, body, org_id, project_id)
        VALUES (
          'WorkOrder','wo-1001',
          '{"summary":"A区巡检知识","fields":{"sla":"4h"}}'::jsonb,
          'dev-org','dev-project'
        )
        ON CONFLICT DO NOTHING
        """
    )
    conn.execute(
        """
        INSERT INTO funnel_status (object_type, stage, detail)
        VALUES ('WorkOrder','enrich','{"stages":["ingest","normalize","enrich","publish"]}'::jsonb)
        ON CONFLICT (object_type) DO NOTHING
        """
    )


def seed_workorders(*, repair: bool = True) -> int:
    """灌入 WorkOrder ObjectType + 5 条样例 + 关联 + wiki + funnel + FGA tuples。

    Args:
        repair: True 时强制刷新样例工单的 props（保持稳定，用于 Inbox filter / 冲突测试）。

    Returns:
        写入的 WorkOrder 样例数。
    """
    from aos_api.db import connect

    with connect() as conn:
        _ensure_workorder_object_type(conn)
        _ensure_site_object_type(conn)
        count = _ensure_sample_workorders(conn, repair=repair)
        _ensure_graph_edges(conn)
        _ensure_fga_demo(conn)
        _ensure_wiki_and_funnel(conn)
        conn.commit()

    log.info(
        "seed_workorders_done samples=%s repair=%s",
        count,
        repair,
    )
    return int(count)
