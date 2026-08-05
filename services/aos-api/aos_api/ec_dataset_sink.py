"""D1-W2: G4 DatasetSink — executor 输出落地到 meta_dataset + DatasetBuild。

骨架阶段：使用 eng.create_dataset（当前合成模式），与原 ec_live_executor 行为等价。
Worker W2 实现：加 data_os_store.persist_dataset + persist_dataset_history + engine.add_build。
"""

from __future__ import annotations

from typing import Any


def sink_to_dataset(
    eng: Any,
    scope: Any,
    pipeline: Any,
    output_rows: list[dict[str, Any]],
) -> Any:
    """将输出行落地为 Dataset，返回 dataset 对象。

    骨架：调用 eng.create_dataset（与原 ec_live_executor 行为等价）。
    W2 实现后：加 persist_dataset + persist_dataset_history + add_build。
    """
    return eng.create_dataset(scope, name=f"pipeline-{pipeline.id}-output")
