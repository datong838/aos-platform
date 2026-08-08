"""D1-W2: G4 DatasetSink — executor 输出落地到 meta_dataset + DatasetBuild。

骨架阶段：使用 eng.create_dataset（当前合成模式），与原 ec_live_executor 行为等价。
Worker W2 实现：加 data_os_store.persist_dataset + persist_dataset_history + engine.add_build。
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from aos_api import data_os_store
from aos_api.phase5_pipeline_engine import DatasetBuild

log = logging.getLogger(__name__)


def _gen_rid() -> str:
    """生成 rid，格式 ri.dataset.<8 字符十六进制>（与 wave_ext.create_pipeline 模式一致）。"""
    return f"ri.dataset.{uuid.uuid4().hex[:8]}"


# Pipeline ID 前缀 → OT 名称（与 ec_normalizer._PIPELINE_ID_TO_OT 对齐）
_PID_TO_OT: dict[str, str] = {
    "p01": "Shop",
    "p02": "Product",
    "p03": "ProductSku",
    "p04": "Category",
    "p05": "Order",
    "p06": "OrderLine",
    "p07": "Shipment",
    "p08": "CustomerLite",
    "p09": "Weapp",
    "p10": "SystemConfig",
    "p11": "ProductReview",
    "p12": "Payment",
}


def _resolve_ot_hint(pipeline: Any) -> str:
    """从 pipeline.config.target_ot 或 pipeline.id 前缀推断 OT hint。"""
    config = getattr(pipeline, "config", None) or {}
    if isinstance(config, dict) and config.get("target_ot"):
        return str(config["target_ot"])
    pid = str(getattr(pipeline, "id", "") or "").lower()
    for prefix, ot in _PID_TO_OT.items():
        if pid.startswith(prefix):
            return ot
    return ""


def sink_to_dataset(
    eng: Any,
    scope: Any,
    pipeline: Any,
    output_rows: list[dict[str, Any]],
) -> Any:
    """将输出行落地为 Dataset，返回 dataset 对象。

    流程（FR-D1-1）:
      1. 生成 rid（ri.dataset.<uuid8>）
      2. eng.create_dataset 创建 Dataset（ds.id == rid，向后兼容骨架）
      3. eng.add_build 记录 DatasetBuild（rows_written = len(output_rows)，非负整数）
      4. data_os_store.persist_dataset 落地 meta_dataset（scope 守门由内部 *scope.key 保证）
      5. data_os_store.persist_dataset_history 落地历史
    容错：persist 失败降级为 warning 不阻塞 sink 流程（与 wave_ext._persist_safe 一致）。
    """
    rid = _gen_rid()
    rows_written = max(0, len(output_rows))
    name = f"pipeline-{getattr(pipeline, 'id', '?')}-output"

    # 1. 创建 Dataset（骨架行为，向后兼容）。ds.id == rid 让 ec_live_executor
    #    不修改即可产出 dataset://catalog/<rid> 格式 output_ref，且
    #    dataset_resolver 通过 ds.id == rid 验证通过。
    ds = eng.create_dataset(scope, name=name, id=rid)

    # 2. 记录 DatasetBuild（add_build 签名为 (scope, dataset_id, **kwargs)，
    #    kwargs 不能含 dataset_id，由内部 DatasetBuild(dataset_id=dataset_id, **kwargs) 注入）
    try:
        eng.add_build(
            scope,
            ds.id,
            status="success",
            rows_written=rows_written,
            finished_at=time.time(),
        )
    except Exception:  # noqa: BLE001
        log.warning("ec_dataset_sink_add_build_failed rid=%s", rid, exc_info=True)

    # 3. 落地 meta_dataset（scope 守门由 persist_dataset 内部 *scope.key 保证）
    #    objectTypeHint 让前端 datasets/preview 能通过 hint 查询 OT 数据
    now = time.time()
    ot_hint = _resolve_ot_hint(pipeline)
    item = {
        "rid": rid,
        "name": name,
        "displayName": name,
        "pipelineId": getattr(pipeline, "id", ""),
        "status": "READY",
        "objectTypeHint": ot_hint,
        "createdAt": now,
        "updatedAt": now,
    }
    try:
        data_os_store.persist_dataset(scope, item)
    except Exception:  # noqa: BLE001
        log.warning("ec_dataset_sink_persist_failed rid=%s", rid, exc_info=True)

    # 4. 落地 dataset_history
    try:
        data_os_store.persist_dataset_history(
            scope,
            rid,
            [{"version": 1, "status": "SUCCEEDED", "at": now, "rowsWritten": rows_written}],
        )
    except Exception:  # noqa: BLE001
        log.warning("ec_dataset_sink_history_failed rid=%s", rid, exc_info=True)

    return ds
