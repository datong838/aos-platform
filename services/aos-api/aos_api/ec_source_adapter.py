"""D1-W1: Niushop SourceAdapter — 从只读源读取行流。

骨架阶段：回退到合成 fixture（sample_input 透传），与原 ec_live_executor 行为等价。
Worker W1 实现：切换到 Niushop 只读 MySQL 源（meta_source 查连接配置 + READ ONLY 事务）。
"""

from __future__ import annotations

from typing import Any


def fetch_source_rows(
    *,
    pipeline: Any,
    nodes: list[Any],
    node_id: str | None,
    sample_input: Any,
    scope: Any = None,
) -> list[dict[str, Any]]:
    """从源读取行流。

    骨架：从 sample_input 构造行流（与原 ec_live_executor 行为等价）。
    W1 实现后：从 Niushop 只读源按游标增量读取。
    """
    if isinstance(sample_input, dict):
        return [sample_input]
    elif isinstance(sample_input, list):
        return [r for r in sample_input if isinstance(r, dict)]
    return []
