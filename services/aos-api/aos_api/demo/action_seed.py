"""动作类型模板种子：已安装 Action 插件 → meta_action_type。

从原 ``action_template_registry.seed_installed_action_types`` 搬迁而来。
仅在 ``demo.seed_test_org()`` 时调用。
"""
from __future__ import annotations

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.action_seed")


def seed_action_types() -> int:
    """幂等灌入已安装 Action 模板到 meta_action_type。

    Returns:
        灌入的模板数量。
    """
    from aos_api.action_template_registry import seed_installed_action_types

    seeded = seed_installed_action_types()
    log.info("seed_action_types_done count=%s", len(seeded))
    return len(seeded)
