"""Workshop Phase 1 seed orchestrator.

Runs all 9 workshop seed functions in order.
Total: 9 modules + 16 widgets + 3 themes + 9 canvas configs + 108 widget instances
     + 30 events + 20 queries + ~50 variables + 9 interfaces + 27 deployments
"""
from __future__ import annotations

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_workshop")


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
