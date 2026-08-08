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
    """确保 PipelineEngine 单例已注入 ecom_consistency_store（O1-A fail-closed 修复）。

    行为：
    1. 已注入（getattr 返回非 None）→ 跳过（idempotent）
    2. 未注入 → 从 db.get_dsn() 装配：
       - create_engine(dsn) + EcomConsistencyStore(engine)
       - setattr(eng, "ecom_consistency_store", store)
    3. 装配失败 → **fail-closed**：抛 RuntimeError，Pipeline 不得在权威层缺失时继续

    O1-A 变更：
    - 删除 `ecom_metadata.create_all()` — 迁移由 Alembic 管理，禁止运行时 DDL
    - 失败从 warning（fail-open）改为 raise RuntimeError（fail-closed）
    """
    if getattr(eng, "ecom_consistency_store", None) is not None:
        return
    try:
        from sqlalchemy import create_engine

        from aos_api.db import get_dsn
        from aos_api.ecom_consistency_store import EcomConsistencyStore

        dsn = get_dsn()
        # psycopg → sqlalchemy 格式
        pg_dsn = dsn
        if pg_dsn.startswith("postgresql://"):
            pg_dsn = "postgresql+psycopg://" + pg_dsn[len("postgresql://"):]
        elif pg_dsn.startswith("postgres://"):
            pg_dsn = "postgresql+psycopg://" + pg_dsn[len("postgres://"):]

        pg_engine = create_engine(pg_dsn)
        # O1-A: 禁止 metadata.create_all — 迁移由 Alembic 管理
        eng.ecom_consistency_store = EcomConsistencyStore(pg_engine)
        log.info("ecom_consistency_store assembled and injected to engine")
    except Exception as exc:
        # O1-A: fail-closed — 权威层装配失败时，Pipeline 必须终止
        raise RuntimeError(
            f"ecom_consistency_store assembly failed — pipeline cannot continue "
            f"without authoritative store (fail-closed). Error: {exc}"
        ) from exc


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

    # O1-A fail-closed: 装配 ecom_consistency_store（失败抛异常终止 Pipeline）
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

        # sink: obj_instance（前端 analytics preview 需要查 obj_instance 表）
        _write_obj_instances(scope, pipeline, output_rows)

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


def _write_obj_instances(scope: Any, pipeline: Any, output_rows: list[dict[str, Any]]) -> None:
    """将 normalized rows 写入 obj_instance 表（供前端 analytics preview 查询）。

    与 wave_ext._execute_pipeline_once 的 obj_instance 写入逻辑对齐：
    - 注册 OT 到 meta_object_type（不存在则创建）
    - full mode 清空旧数据后批量插入
    - props 存储所有字段（全字段保留映射）
    容错：写入失败降级为 warning 不阻塞 sink 流程。
    """
    if not output_rows:
        return

    # 推断 target_ot
    from aos_api.ec_normalizer import _resolve_target_ot

    object_type = _resolve_target_ot(pipeline)
    if not object_type:
        log.warning("obj_instance_skip no target_ot pipeline=%s", getattr(pipeline, "id", "?"))
        return

    import json as _json
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope

    org_id = getattr(scope, "org_id", "") or ""
    project_id = getattr(scope, "project_id", "") or ""
    if not org_id or not project_id:
        return

    try:
        instances: list[tuple[str, str, str, str, str]] = []
        for row in output_rows:
            oid = str(row.get("source_pk") or row.get("id") or "")
            if not oid:
                continue
            # 排除 Link 行（link type 以 _link 结尾或含 link_type 字段）
            if row.get("link_type"):
                continue
            props = {k: v for k, v in row.items() if k not in ("link_type",)}
            instances.append((
                object_type, oid,
                _json.dumps(props, ensure_ascii=False, default=str),
                org_id, project_id,
            ))

        if not instances:
            return

        write_scope = TenantScope(org_id, project_id)
        pipeline_id = str(getattr(pipeline, "id", ""))
        with connect(write_scope) as conn:
            with conn.cursor() as cur:
                ds_name = (str(getattr(pipeline, "name", "")) or pipeline_id or object_type)[:200]
                cur.execute(
                    """INSERT INTO meta_object_type (id, name, description, published, properties)
                       VALUES (%s, %s, %s, TRUE, '{}'::jsonb)
                       ON CONFLICT (id) DO NOTHING""",
                    (object_type, ds_name, f"auto-registered by pipeline {pipeline_id}"),
                )
                # full mode: 清空旧数据
                cur.execute(
                    "DELETE FROM obj_instance WHERE object_type=%s AND org_id=%s AND project_id=%s",
                    (object_type, org_id, project_id),
                )
                cur.executemany(
                    """INSERT INTO obj_instance (object_type, object_id, props, org_id, project_id)
                       VALUES (%s, %s, %s::jsonb, %s, %s)
                       ON CONFLICT (org_id, project_id, object_type, object_id) DO UPDATE
                         SET props = EXCLUDED.props""",
                    instances,
                )
            conn.commit()
        log.info("obj_instance_written ot=%s count=%d pipeline=%s", object_type, len(instances), pipeline_id)
    except Exception:
        log.warning("obj_instance_write_failed pipeline=%s", getattr(pipeline, "id", "?"), exc_info=True)
