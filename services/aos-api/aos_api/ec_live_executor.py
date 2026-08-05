"""G2: 生产 executor — ec-live-v1.

处理 execution_mode="live" 的电商管道。
Phase A 骨架重构后，source/sink/异常 分发到独立模块：
- ec_source_adapter: Niushop 只读源读取（W1）
- ec_dataset_sink: Dataset 落地（G4/W2）
- ec_ot_writer: OT + Link 落地（G5/W3）
- ec_dlq_handler: DLQ 投递（G6/W4）

Phase B transform 节点拆分到独立模块：
- ec_derived_metrics: 派生指标计算（W1）
- ec_link_builder: 核心 Link 行构造（W3）
"""

from __future__ import annotations

from typing import Any

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.ec_source_adapter import fetch_source_rows
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.ec_dlq_handler import handle_failure
from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_link_builder import build_link_rows


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

    try:
        # source: 从 Niushop 只读源读取（W1 实现）
        input_rows = fetch_source_rows(
            pipeline=pipeline,
            nodes=nodes,
            node_id=node_id,
            sample_input=sample_input,
            scope=scope,
        )

        # transform: 透传 + 派生指标 + Link 构造（Phase B 拆分到独立模块）
        #   1. 浅拷贝避免污染 source 行
        #   2. apply_derived_metrics: 按 target_ot 计算 4 个派生指标写入 row（W1）
        #   3. build_link_rows: 按 target_ot 构造 6 条核心 Link 行追加到 rows（W3）
        output_rows = [dict(row) for row in input_rows]
        output_rows = apply_derived_metrics(output_rows, pipeline)
        output_rows = build_link_rows(output_rows, pipeline)

        # sink: Dataset（G4，W2 实现）
        ds = sink_to_dataset(eng, scope, pipeline, output_rows)

        # sink: OT + Link（G5，W3 实现）
        sink_to_ot(eng, scope, pipeline, output_rows)

        return {
            "input_ref": "",
            "output_ref": f"dataset://catalog/{ds.id}",
            "lineage_ref": "",
            "quality_ref": "",
            "rows_read": len(input_rows),
            "rows_written": len(output_rows),
            "output_rows": output_rows,
        }

    except Exception as exc:
        # G6 DLQ（W4 实现）
        handle_failure(pipeline, scope, exc)
        raise
