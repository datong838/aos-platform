"""模块列表种子：测试组织下的 Workshop Module 列表。

从原 ``module_store.seed_modules_if_empty`` 搬迁而来。仅在 ``demo.seed_test_org()`` 时调用。
"""
from __future__ import annotations

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.module_seed")


def seed_modules() -> int:
    """幂等灌入 dev-org / dev-project 下的 Workshop Module 列表。

    Returns:
        模块数量。
    """
    from aos_api.module_store import seed_modules_if_empty

    seed_modules_if_empty()
    log.info("seed_modules_done")
    return 3
