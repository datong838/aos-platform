"""Seed module events — Phase 1 Workshop backend.

30 event bindings: 6 trigger types × 5 modules.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_events import ensure_events_schema

log = get_logger("aos-api.demo.seed_module_events")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_TRIGGERS = [
    {"type": "on_click", "label": "点击刷新", "action_type": "query", "action_target": "object_table"},
    {"type": "on_select", "label": "选择联动", "action_type": "set_variable", "action_target": "selectedIds"},
    {"type": "on_change", "label": "值变更查询", "action_type": "query", "action_target": "filter_query"},
    {"type": "on_load", "label": "加载初始化", "action_type": "query", "action_target": "init_data"},
    {"type": "interval", "label": "定时轮询", "action_type": "query", "action_target": "refresh", "value": 30},
    {"type": "custom", "label": "自定义触发", "action_type": "call_function", "action_target": "process"},
]

_TARGET_MODULES = [
    "dev-module-order",
    "dev-module-risk",
    "dev-module-customer",
    "dev-module-analysis",
    "dev-module-workorder",
]


def seed_module_events() -> int:
    """Idempotently seed 30 event bindings. Returns count."""
    ensure_events_schema()
    count = 0
    with connect() as conn:
        # Clear our dev-module-* event seeds
        conn.execute(
            """
            DELETE FROM module_events
             WHERE module_id LIKE 'dev-module-%%' AND org_id=%s
            """,
            (_DEFAULT_ORG,),
        )

        for module_id in _TARGET_MODULES:
            for i, t in enumerate(_TRIGGERS):
                eid = f"evt-{module_id}-{t['type']}"
                trigger = {"type": t["type"]}
                if "value" in t:
                    trigger["value"] = t["value"]
                    trigger["unit"] = "seconds"
                action = {"type": t["action_type"], "target": t["action_target"]}
                conn.execute(
                    """
                    INSERT INTO module_events (
                        id, module_id, name, trigger_config, action_config,
                        enabled, sort_order, org_id, project_id
                    ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name=EXCLUDED.name, trigger_config=EXCLUDED.trigger_config,
                        action_config=EXCLUDED.action_config, enabled=EXCLUDED.enabled
                    """,
                    (
                        eid,
                        module_id,
                        t["label"],
                        json.dumps(trigger),
                        json.dumps(action),
                        True,
                        i,
                        _DEFAULT_ORG,
                        _DEFAULT_PROJECT,
                    ),
                )
                count += 1

        conn.commit()
    log.info("seed_module_events_done count=%s", count)
    return count
