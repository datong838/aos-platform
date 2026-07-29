"""Seed module variables — Phase 1 Workshop backend.

W1-A1: group_name 存作用域 page/app/global，供 Variables 页 scope Tab 过滤。
覆盖 string/number/array/boolean/object 类型；主模块全量 + 其余模块各 1 条。
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_variables import ensure_schema

log = get_logger("aos-api.demo.seed_module_variables")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_MODULE_IDS = [
    "dev-module-order",
    "dev-module-risk",
    "dev-module-customer",
    "dev-module-asset",
    "dev-module-analysis",
    "dev-module-workorder",
    "dev-module-inventory",
    "dev-module-finance",
    "dev-module-marketing",
]

# (var_type, scope/group, name, init, desc)
_PRIMARY_VARS: list[tuple[str, str, str, object, str]] = [
    ("string", "page", "selectedStatus", "all", "当前选中状态"),
    ("string", "page", "searchKeyword", "", "搜索关键词"),
    ("string", "page", "currentTab", "all", "当前 Tab"),
    ("number", "page", "pageSize", 20, "每页条数"),
    ("number", "page", "currentPage", 1, "当前页码"),
    ("number", "page", "totalCount", 0, "总条数"),
    ("array", "page", "selectedIds", [], "选中 ID 列表"),
    ("array", "page", "tableData", [], "表格数据"),
    ("boolean", "page", "loading", False, "加载状态"),
    ("boolean", "page", "showDetail", False, "显示详情"),
    ("object", "page", "filterParams", {}, "筛选参数"),
    ("object", "page", "detailData", {}, "详情数据"),
    ("string", "app", "appTheme", "light", "应用主题"),
    ("number", "app", "notificationCount", 0, "通知数量"),
    ("object", "app", "currentUser", {"id": "demo"}, "当前用户"),
    ("string", "global", "ENV", "production", "运行环境"),
    ("string", "global", "API_BASE_URL", "https://aos-api.internal/v1", "API 基址"),
]


def seed_module_variables() -> int:
    """Idempotently seed variables with page/app/global scopes. Returns count."""
    ensure_schema()
    count = 0
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM module_variable
             WHERE module_id LIKE 'dev-module-%%' AND org_id=%s
            """,
            (_DEFAULT_ORG,),
        )

        primary = _MODULE_IDS[0]
        for idx, (var_type, scope, name, init_val, desc) in enumerate(_PRIMARY_VARS):
            vid = f"var-{primary}-{idx + 1}"
            conn.execute(
                """
                INSERT INTO module_variable (
                    id, module_id, name, var_type, group_name,
                    initial_value, current_value, description, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, var_type=EXCLUDED.var_type,
                    group_name=EXCLUDED.group_name,
                    initial_value=EXCLUDED.initial_value,
                    current_value=EXCLUDED.current_value,
                    description=EXCLUDED.description
                """,
                (
                    vid,
                    primary,
                    name,
                    var_type,
                    scope,
                    json.dumps(init_val),
                    json.dumps(init_val),
                    desc,
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
            count += 1

        # 其余模块各 1 条 page 作用域变量，保证切换 module 可见数据
        for module_id in _MODULE_IDS[1:]:
            vid = f"var-{module_id}-1"
            conn.execute(
                """
                INSERT INTO module_variable (
                    id, module_id, name, var_type, group_name,
                    initial_value, current_value, description, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, group_name=EXCLUDED.group_name,
                    initial_value=EXCLUDED.initial_value,
                    current_value=EXCLUDED.current_value
                """,
                (
                    vid,
                    module_id,
                    "selectedStatus",
                    "string",
                    "page",
                    json.dumps("all"),
                    json.dumps("all"),
                    "当前选中状态",
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
            count += 1

        conn.commit()
    log.info("seed_module_variables_done count=%s", count)
    return count
