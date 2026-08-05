"""G2: 生产 executor — ec-live-v1.

处理 execution_mode="live" 的电商管道。
Phase A 骨架重构后，source/sink/异常 分发到独立模块：
- ec_source_adapter: Niushop 只读源读取（W1）
- ec_dataset_sink: Dataset 落地（G4/W2）
- ec_ot_writer: OT + Link 落地（G5/W3）
- ec_dlq_handler: DLQ 投递（G6/W4）
"""

from __future__ import annotations

from typing import Any

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.ec_source_adapter import fetch_source_rows
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.ec_dlq_handler import handle_failure


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

        # transform: 透传（Phase B 加 Normalize/Validate/Deduplicate）
        output_rows = [dict(row) for row in input_rows]

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
