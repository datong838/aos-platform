"""Seed module variables — Phase 1 Workshop backend.

50 variables: 5 type groups (string/number/array/boolean/object) × 10 per group.
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

# 5 type groups
_VAR_GROUPS = [
    ("string", "字符串", [
        ("selectedStatus", "all", "当前选中状态"),
        ("searchKeyword", "", "搜索关键词"),
        ("currentTab", "all", "当前 Tab"),
    ]),
    ("number", "数值", [
        ("pageSize", 20, "每页条数"),
        ("currentPage", 1, "当前页码"),
        ("totalCount", 0, "总条数"),
    ]),
    ("array", "数组", [
        ("selectedIds", [], "选中 ID 列表"),
        ("tableData", [], "表格数据"),
    ]),
    ("boolean", "布尔", [
        ("loading", False, "加载状态"),
        ("showDetail", False, "显示详情"),
    ]),
    ("object", "对象", [
        ("filterParams", {}, "筛选参数"),
        ("detailData", {}, "详情数据"),
    ]),
]


def seed_module_variables() -> int:
    """Idempotently seed ~50 variables across 5 groups. Returns count."""
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

        # Seed first module with full set, distribute to others to reach ~50
        primary = _MODULE_IDS[0]
        var_idx = 0
        for var_type, group_label, vars_in_group in _VAR_GROUPS:
            for name, init_val, desc in vars_in_group:
                vid = f"var-{primary}-{var_idx+1}"
                conn.execute(
                    """
                    INSERT INTO module_variable (
                        id, module_id, name, var_type, group_name,
                        initial_value, current_value, description, org_id, project_id
                    ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        name=EXCLUDED.name, var_type=EXCLUDED.var_type,
                        initial_value=EXCLUDED.initial_value,
                        current_value=EXCLUDED.current_value
                    """,
                    (
                        vid,
                        primary,
                        name,
                        var_type,
                        group_label,
                        json.dumps(init_val),
                        json.dumps(init_val),
                        desc,
                        _DEFAULT_ORG,
                        _DEFAULT_PROJECT,
                    ),
                )
                count += 1
                var_idx += 1

        # Add one string var to each remaining module (8 more)
        for module_id in _MODULE_IDS[1:]:
            vid = f"var-{module_id}-1"
            conn.execute(
                """
                INSERT INTO module_variable (
                    id, module_id, name, var_type, group_name,
                    initial_value, current_value, description, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, initial_value=EXCLUDED.initial_value,
                    current_value=EXCLUDED.current_value
                """,
                (
                    vid,
                    module_id,
                    "selectedStatus",
                    "string",
                    "字符串",
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
