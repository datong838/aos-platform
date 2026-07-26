"""[Deprecated · 测试辅助] Wave-0 内存 Mock — 仅保留 reset 辅助。

**重要变更**：本模块已不再被生产代码引用：
- ``routers/object_sets.py`` 只走真实 PG（移除 ``source=mock`` 参数和 fallback）
- ``vector_index.py`` 移除 mock fallback，PG 不可用时返回空
- ``tool_runtime.py`` ``query.objects`` 工具改为真实 PG 查询
- Phase 6 (v2.3) 已删除 list_modules / get_module / create_module / update_module /
  publish_module / module_runtime / query_objects 7 个 0 引用 CRUD 函数 + _OBJECTS 列表

保留本模块的原因：
- 28 个单测 + conftest 在 setup 时调用 ``mock_data.reset_mock_state()`` 作为清理动作。
- 全局 grep 确认：生产代码（aos_api/ 内）0 引用，main.py 启动流程不调用，纯测试辅助。
- 后续单测可逐步改用 ``from aos_api.demo import clear_test_org`` 替代，最终删除本文件。
"""
from __future__ import annotations

from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.mock")

_MODULES: list[dict[str, Any]] = [
    {
        "id": "mod-ops-inbox",
        "name": "运营台 Inbox",
        "status": "published",
        "description": "Demo-aligned Module for Workshop Inbox",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/inbox",
        "widgets": ["table", "filters", "selection"],
        "buddyBound": True,
    },
    {
        "id": "mod-canvas-draft",
        "name": "画布草稿",
        "status": "draft",
        "description": "Canvas editor placeholder",
        "objectType": "WorkOrder",
        "markings": ["restricted"],
        "entryPath": "/workshop/canvas",
        "widgets": ["canvas"],
        "buddyBound": False,
    },
    {
        "id": "mod-buddy-assist",
        "name": "Buddy 助手",
        "status": "published",
        "description": "AIP Assist Module",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/buddy",
        "widgets": ["chat"],
        "buddyBound": True,
    },
]


def reset_mock_state() -> None:
    """[测试辅助] 清空内存 module 列表，重建已知 id。

    仅供单测 setup 调用；新测试建议改用 ``from aos_api.demo import clear_test_org``。
    """
    global _MODULES
    seed_ids = {"mod-ops-inbox", "mod-canvas-draft", "mod-buddy-assist"}
    _MODULES[:] = [m for m in _MODULES if m["id"] in seed_ids]
    if not any(m["id"] == "mod-buddy-assist" for m in _MODULES):
        _MODULES.append(
            {
                "id": "mod-buddy-assist",
                "name": "Buddy 助手",
                "status": "published",
                "description": "AIP Assist Module",
                "objectType": "WorkOrder",
                "markings": ["public"],
                "entryPath": "/workshop/buddy",
                "widgets": ["chat"],
                "buddyBound": True,
            }
        )
    log.debug("mock_reset modules=%s", len(_MODULES))
