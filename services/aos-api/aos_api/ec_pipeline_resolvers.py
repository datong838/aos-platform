"""G3: Pipeline evidence resolver — 生产注册版。

dataset_resolver 查 engine._datasets 内存 store 验证 dataset 存在性。
scope 隔离靠写入侧 create_dataset(scope, ...) 保障；resolver 做 rid 全局存在性检查。
object_resolver / lineage_resolver / quality_resolver 延后到对应存储就绪后注册。
"""

from __future__ import annotations

from urllib.parse import urlparse

from aos_api.phase5_pipeline_engine import get_engine


def _parse_dataset_rid(ref: str) -> str | None:
    try:
        parsed = urlparse(ref)
    except Exception:
        return None
    if parsed.scheme != "dataset":
        return None
    if not parsed.netloc:
        return None
    path = parsed.path.lstrip("/")
    if not path:
        return None
    return path


def dataset_resolver(ref: str) -> bool:
    """验证 dataset://catalog/<rid> 指向的 dataset 在 engine 中真实存在。"""
    rid = _parse_dataset_rid(ref)
    if rid is None:
        return False
    try:
        eng = get_engine()
        for ds in eng._datasets.values():
            if ds.id == rid:
                return True
        return False
    except Exception:
        return False
