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

D2.5 架构缺口修复：
- ec_normalizer: raw ns_xxx 行 → OT normalized 行（缺口 1 修复）
- ensure_store_assembled: PipelineEngine 单例自动注入 ecom_consistency_store（缺口 2 修复）
"""

from __future__ import annotations

from typing import Any

from aos_api.logging_facade import get_logger
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.ec_source_adapter import fetch_source_rows
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.ec_dlq_handler import handle_failure
from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_link_builder import build_link_rows
from aos_api.ec_normalizer import normalize_rows

log = get_logger("aos-api.ec-live-executor")


def ensure_store_assembled(eng: Any) -> None:
    """确保 PipelineEngine 单例已注入 ecom_consistency_store（D2.5 缺口 2 修复）。

    行为：
    1. 已注入（getattr 返回非 None）→ 跳过（idempotent）
    2. 未注入 → 尝试从 db.get_dsn() 装配：
       - create_engine(dsn) + EcomConsistencyStore(engine)
       - setattr(eng, "ecom_consistency_store", store)
    3. 装配失败（测试环境无 PG / DSN 缺失）→ 记 warning 日志，保持骨架行为
       （sink_to_ot 自身有 store=None 零计数分支，不抛异常）

    设计权衡：
    - 不在 PipelineEngine.__new__ 里装配：避免单例依赖 db engine，破坏单测
    - 失败降级而非 fail-closed：测试环境（无 PG）仍能跑 ec_live_executor 链路
    """
    if getattr(eng, "ecom_consistency_store", None) is not None:
        return
    try:
        from sqlalchemy import create_engine

        from aos_api.db import get_dsn
        from aos_api.ecom_consistency_store import (
            EcomConsistencyStore,
            metadata as ecom_metadata,
        )

        dsn = get_dsn()
        # psycopg → sqlalchemy 格式
        pg_dsn = dsn
        if pg_dsn.startswith("postgresql://"):
            pg_dsn = "postgresql+psycopg://" + pg_dsn[len("postgresql://"):]
        elif pg_dsn.startswith("postgres://"):
            pg_dsn = "postgresql+psycopg://" + pg_dsn[len("postgres://"):]

        pg_engine = create_engine(pg_dsn)
        ecom_metadata.create_all(pg_engine)  # 已存在则 no-op
        eng.ecom_consistency_store = EcomConsistencyStore(pg_engine)
        log.info("ecom_consistency_store assembled and injected to engine")
    except Exception as exc:
        # 测试环境或 DSN 缺失：降级为骨架行为（sink_to_ot 自身有零计数分支）
        log.warning("ecom_consistency_store assembly skipped: %s", exc)


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

    # D2.5 缺口 2 修复：装配 ecom_consistency_store（失败降级，不抛异常）
    ensure_store_assembled(eng)

    try:
        # source: 从 Niushop 只读源读取（W1 实现）
        input_rows = fetch_source_rows(
            pipeline=pipeline,
            nodes=nodes,
            node_id=node_id,
            sample_input=sample_input,
            scope=scope,
        )

        # transform: normalize + 派生指标 + Link 构造（Phase B 拆分到独立模块）
        #   1. D2.5 缺口 1 修复：normalize_rows 将 raw ns_xxx 行转为 OT normalized 行（幂等）
        #   2. 浅拷贝避免污染 source 行
        #   3. apply_derived_metrics: 按 target_ot 计算 4 个派生指标写入 row（W1）
        #   4. build_link_rows: 按 target_ot 构造 6 条核心 Link 行追加到 rows（W3）
        normalized_rows = normalize_rows(input_rows, pipeline)
        output_rows = [dict(row) for row in normalized_rows]
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
