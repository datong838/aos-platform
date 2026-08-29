"""Workshop Phase 1 seed orchestrator.

Runs all 9 workshop seed functions in order.
Total: 9 modules + 16 widgets + 3 themes + 9 canvas configs + 108 widget instances
     + 30 events + 20 queries + ~50 variables + 9 interfaces + 27 deployments
"""
from __future__ import annotations

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_workshop")


def _ensure_seed_scope() -> None:
    """Persist the disposable Workshop demo workspace before child seeds."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_org (id, name, kind, join_policy, discoverable)
            VALUES ('dev-org', '开发测试组织', 'standard', 'invite_or_apply', TRUE)
            ON CONFLICT (id) DO NOTHING
            """
        )
        conn.execute(
            """
            INSERT INTO meta_workspace
              (org_id, project_id, name, deletable, kind)
            VALUES ('dev-org', 'dev-project', '默认工作区', TRUE, 'default')
            ON CONFLICT (org_id, project_id) DO NOTHING
            """
        )
        conn.commit()


def seed_workshop() -> dict[str, int]:
    """Run all Workshop Phase 1 seeds idempotently. Returns counts."""
    from aos_api.demo.seed_module_deployments import seed_module_deployments
    from aos_api.demo.seed_module_events import seed_module_events
    from aos_api.demo.seed_module_interfaces import seed_module_interfaces
    from aos_api.demo.seed_module_queries import seed_module_queries
    from aos_api.demo.seed_module_variables import seed_module_variables
    from aos_api.demo.seed_module_widgets import seed_module_widgets
    from aos_api.demo.seed_modules_ext import seed_modules
    from aos_api.demo.seed_themes import seed_themes
    from aos_api.demo.seed_widgets import seed_widgets

    log.info("seed_workshop_start")

    # Workshop catalog tables are tenant-owned and reference the composite
    # workspace root.  Establish the disposable demo scope before seeding any
    # child rows so a freshly migrated database remains FK-correct.
    _ensure_seed_scope()

    result = {
        "modules": seed_modules(),
        "widgets": seed_widgets(),
        "themes": seed_themes(),
        "canvasConfigsAndInstances": seed_module_widgets(),
        "events": seed_module_events(),
        "queries": seed_module_queries(),
        "variables": seed_module_variables(),
        "interfaces": seed_module_interfaces(),
        "deployments": seed_module_deployments(),
    }
    log.info("seed_workshop_done %s", result)
    return result
