"""测试组织数据种子总入口。

按顺序：
  1. dev-org / dev-project / 默认人员
  2. 工单 ObjectType + 样例工单 + 关联 + wiki
  3. 订单 ObjectType + 20 条订单
  4. 模块列表 / 动作模板
  5. OpenFGA demo tuples（含 dev-org / dev-project）
  6. Apollo catalog seed（系统级，幂等）

所有写入只针对 dev-org / dev-project，与企业正式组织数据物理隔离。
"""
from __future__ import annotations

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed")


def seed_test_org(*, repair: bool = True) -> dict[str, str | int]:
    """灌入一套完整的测试组织数据（幂等）。

    幂等保证：所有写入都用 ``ON CONFLICT DO NOTHING`` 或 ``DO UPDATE``，
    重复执行不会重复插入，但 ``repair=True`` 时会强制刷新 WorkOrder 样例 props。

    Returns:
        各子种子结果计数。
    """
    from aos_api.demo.action_seed import seed_action_types
    from aos_api.demo.module_seed import seed_modules
    from aos_api.demo.order_seed import seed_orders
    from aos_api.demo.org_seed import seed_org_members
    from aos_api.demo.workorder_seed import seed_workorders

    log.info("seed_test_org_start repair=%s", repair)

    org_count = seed_org_members()
    wo_count = seed_workorders(repair=repair)
    order_count = seed_orders()
    module_count = seed_modules()
    action_count = seed_action_types()

    result: dict[str, str | int] = {
        "ok": True,
        "mode": "seed_test_org",
        "orgMembers": org_count,
        "workorders": wo_count,
        "orders": order_count,
        "modules": module_count,
        "actionTypes": action_count,
    }
    log.info("seed_test_org_done %s", result)
    return result


def clear_test_org() -> dict[str, str | int]:
    """清空 dev-org / dev-project 下的所有测试数据。

    清理范围：
      - obj_instance 中 WorkOrder / Order / OrderItem / Site
      - meta_module / meta_object_type 中的 WorkOrder / Order / OrderItem
      - wiki_page 中 dev-org 的数据
      - graph_edge 中 WorkOrder 关联
      - membership / workspaces_catalog / orgs 中的 dev-org
      - person_identity 中 alice / bob / user:dev
      - draft_dataset / decision_lineage 中 dev-org 的数据

    注意：此函数会删除数据，仅在回归清理或重置测试环境时调用。
    """
    from aos_api.db import connect

    log.warning("clear_test_org_start (destructive)")

    removed: dict[str, str | int] = {"ok": True, "mode": "clear_test_org"}
    with connect() as conn:
        for object_type in ("WorkOrder", "Order", "OrderItem", "Site"):
            cur = conn.execute(
                "DELETE FROM obj_instance WHERE object_type = %s",
                (object_type,),
            )
            removed[f"obj_{object_type}"] = int(cur.rowcount or 0)

        conn.execute(
            """
            DELETE FROM graph_edge
             WHERE src_type IN ('WorkOrder','Order','OrderItem','Site')
                OR dst_type IN ('WorkOrder','Order','OrderItem','Site')
            """
        )

        conn.execute("DELETE FROM wiki_page WHERE org_id = 'dev-org'")
        conn.execute(
            """
            DELETE FROM meta_module WHERE org_id = 'dev-org'
            """
        )
        conn.execute(
            """
            DELETE FROM meta_object_type
             WHERE id IN ('WorkOrder','Order','OrderItem','Site')
            """
        )
        conn.execute(
            """
            DELETE FROM meta_link_type
             WHERE id IN ('lt-related-to','lt-order-item')
            """
        )

        try:
            cur = conn.execute(
                """
                DELETE FROM draft_dataset WHERE org_id = 'dev-org'
                """
            )
            removed["drafts"] = int(cur.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            removed["drafts"] = f"skip:{exc}"
        try:
            cur = conn.execute(
                """
                DELETE FROM decision_lineage
                 WHERE object_type IN ('WorkOrder','Order','OrderItem','Site')
                """
            )
            removed["lineage"] = int(cur.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            removed["lineage"] = f"skip:{exc}"
        try:
            cur = conn.execute(
                """
                DELETE FROM authz_tuple
                 WHERE object_key LIKE 'organization:dev-org%'
                    OR object_key LIKE 'project:dev-project%'
                    OR object_key LIKE 'object:WorkOrder:%'
                """
            )
            removed["authzTuples"] = int(cur.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            removed["authzTuples"] = f"skip:{exc}"

        try:
            cur = conn.execute(
                "DELETE FROM meta_membership WHERE org_id = 'dev-org'"
            )
            removed["memberships"] = int(cur.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            removed["memberships"] = f"skip:{exc}"
        try:
            cur = conn.execute(
                "DELETE FROM meta_workspace WHERE org_id = 'dev-org'"
            )
            removed["workspaces"] = int(cur.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            removed["workspaces"] = f"skip:{exc}"
        try:
            cur = conn.execute("DELETE FROM meta_org WHERE id = 'dev-org'")
            removed["org"] = int(cur.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            removed["org"] = f"skip:{exc}"

        conn.commit()

    from aos_api import membership as mem
    from aos_api import orgs as org_store
    from aos_api import workspaces_catalog as ws_cat

    org_store.reset_org_store()
    ws_cat.reset_workspace_catalog()
    mem.reset_membership_store()
    try:
        from aos_api.person_identity import reset_person_store

        reset_person_store()
    except Exception:  # noqa: BLE001
        log.exception("reset_person_store_failed_continue")

    log.warning("clear_test_org_done %s", removed)
    return removed
