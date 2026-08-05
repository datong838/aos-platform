"""G2: 生产 executor 骨架 — ec-live-v1。

处理 execution_mode="live" 的电商管道。D1 波次前用合成 fixture（不直连 MySQL）；
D1 波次 SourceAdapter 实例化为 Niushop 只读源。

本方案交付执行链注册与 evidence 闭环；SourceAdapter 真实数据源是 D1 波次配置项。
"""

from __future__ import annotations

from typing import Any

from aos_api.phase5_pipeline_engine import get_engine


def ec_live_executor(
    *,
    pipeline: Any,
    nodes: list[Any],
    node_id: str | None,
    sample_input: Any,
    execution_kind: str,
    cancel_event: Any,
    deadline: float,
    scope: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    eng = get_engine()

    input_rows: list[dict[str, Any]] = []
    if isinstance(sample_input, dict):
        input_rows = [sample_input]
    elif isinstance(sample_input, list):
        input_rows = [r for r in sample_input if isinstance(r, dict)]

    output_rows = [dict(row) for row in input_rows]

    ds = eng.create_dataset(scope, name=f"pipeline-{pipeline.id}-output")

    return {
        "input_ref": "",
        "output_ref": f"dataset://catalog/{ds.id}",
        "lineage_ref": "",
        "quality_ref": "",
        "rows_read": len(input_rows),
        "rows_written": len(output_rows),
        "output_rows": output_rows,
    }
