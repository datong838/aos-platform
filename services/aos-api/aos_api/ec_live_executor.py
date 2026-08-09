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
from aos_api.ec_source_adapter import batch_read_public, fetch_source_rows
from aos_api.ec_dataset_sink import sink_to_dataset
from aos_api.ec_ot_writer import sink_derived_metrics, sink_to_ot
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
    run_id = str(kwargs.get("run_id") or "").strip()

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

        # transform: Payment 权威丰富 + normalize + 派生指标 + Link 构造
        #   1. 浅拷贝 raw source 行，避免污染 SourceAdapter 输出
        #   2. O1-A: Payment 在 normalize 前批量丰富 _order_create_time
        #   3. D2.5: normalize_rows 将 raw ns_xxx 行转为 OT normalized 行（幂等）
        #   4. apply_derived_metrics: 按 target_ot 计算 8 个派生指标写入 row（含 link_aggregator）
        #   5. build_link_rows: 按 target_ot 构造 14 条核心 Link 行追加到 rows
        enriched_input_rows = [dict(row) for row in input_rows]
        _enrich_payment_order_create_time(
            pipeline=pipeline,
            nodes=nodes,
            node_id=node_id,
            scope=scope,
            rows=enriched_input_rows,
        )
        output_rows = normalize_rows(enriched_input_rows, pipeline)

        # O1-A: 构造 link_aggregator（从已写入的 ecom_object/ecom_link 查 Order 聚合数据）
        aggregator = _make_link_aggregator(eng, scope)
        output_rows = apply_derived_metrics(output_rows, pipeline, link_aggregator=aggregator)
        output_rows = build_link_rows(output_rows, pipeline)

        # sink: Dataset（G4，W2 实现）
        ds = sink_to_dataset(eng, scope, pipeline, output_rows)

        # sink: OT + Link（G5，W3 实现）
        sink_to_ot(eng, scope, pipeline, output_rows)

        # O1 §5.2.10：派生属性不得再次整对象覆盖，必须走 CAS/Receipt/Outbox。
        derived = sink_derived_metrics(eng, scope, pipeline, output_rows)

        # O1-R2: 兼容 obj_instance/graph_edge 仅由单一 Projector 消费权威
        # Outbox 后写入；executor 禁止双写或制造事后伪 Outbox。
        from aos_api.ecom_projector import project_pending

        projection = project_pending(scope)

        return {
            "input_ref": "",
            "output_ref": f"dataset://catalog/{ds.id}",
            "lineage_ref": "",
            "quality_ref": "",
            "rows_read": len(input_rows),
            "rows_written": len(output_rows),
            "output_rows": output_rows,
            "projection": projection,
            "derived": derived,
        }

    except Exception as exc:
        # G6 DLQ（W4 实现）
        if run_id:
            handle_failure(pipeline, scope, exc, run_id=run_id)
        else:
            log.error(
                "ec_pipeline_dlq_push_failed pipeline=%s error=RUN_ID_REQUIRED",
                getattr(pipeline, "id", "unknown"),
            )
        raise


# ═══════════════════════════════════════════════════════════════
# O1-A: Payment 丰富 + link_aggregator 工厂
# ═══════════════════════════════════════════════════════════════

def _enrich_payment_order_create_time(
    *,
    pipeline: Any,
    nodes: list[Any],
    node_id: str | None,
    scope: Any,
    rows: list[dict[str, Any]],
) -> None:
    """O1-A §5.2.11：在 normalize 前从 P12 当前 Source 批读 Order 时间。

    连接/契约失败由 `batch_read_public` fail-closed。单个 relate_id 在源
    `ns_order` 不存在时保持空值，后续由 G17 eligible 证据显式报告。
    """
    from aos_api.ec_normalizer import _resolve_target_ot

    target_ot = _resolve_target_ot(pipeline)
    if target_ot != "Payment":
        return

    # 收集 relate_id → row 映射
    id_to_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("link_type"):  # skip link rows
            continue
        relate_id = str(row.get("relate_id") or row.get("order_id") or "").strip()
        if relate_id:
            id_to_rows.setdefault(relate_id, []).append(row)

    if not id_to_rows:
        return

    order_ids = tuple(id_to_rows)
    results = batch_read_public(
        pipeline=pipeline,
        nodes=nodes,
        node_id=node_id,
        scope=scope,
        spec_id="payment_order_time",
        filter_values=order_ids,
    )
    found_ids: set[str] = set()
    for order in results:
        raw_id = str(order.get("order_id") or "").strip()
        created_at = order.get("create_time")
        if not raw_id or created_at in (None, ""):
            continue
        found_ids.add(raw_id)
        for row in id_to_rows.get(raw_id, []):
            row["_order_create_time"] = created_at

    log.info(
        "payment_enriched orders_found=%d/%d pipeline=%s",
        len(found_ids), len(order_ids), getattr(pipeline, "id", "?"),
    )


def _make_link_aggregator(eng: Any, scope: Any) -> Any:
    """O1-A: 构造 link_aggregator 闭包（从 ecom_object 查 Order 聚合数据）。

    返回一个 Callable[[frozenset[str]], dict[str, tuple[int, datetime|None]]]。
    输入 member_ids 集合，返回 {member_id: (order_count, last_created_at)}。
    """
    from datetime import datetime, timezone
    from aos_api.ecom_consistency_store import ecom_object as _tbl, ecom_link as _link_tbl
    from sqlalchemy import select, func, and_
    from sqlalchemy.engine import Engine

    store = getattr(eng, "ecom_consistency_store", None)
    org_id = getattr(scope, "org_id", "") or ""
    workspace_id = getattr(scope, "project_id", "") or getattr(scope, "workspace_id", "") or ""
    engine: Engine = getattr(store, "_engine", None) if store else None

    def aggregator(member_ids: frozenset[str]) -> dict[str, tuple[int, datetime | None]]:
        if not member_ids or engine is None:
            return {}

        try:
            # 查 Order → CustomerLite (placedByLite) link，聚合 order_count + max(createdAt)
            # 从 ecom_object 查 Order 的 properties.createdAt
            # 从 ecom_link 查 placedByLite 关系
            ids_list = list(member_ids)
            with engine.connect() as conn:
                # 设置 GUC
                from sqlalchemy import text as _text

                conn.execute(_text(f"SET LOCAL aos.org_id = '{org_id}'"))
                conn.execute(_text(f"SET LOCAL aos.workspace_id = '{workspace_id}'"))

                # 查 Order objects 的 member_id 和 createdAt
                order_rows = conn.execute(
                    select(
                        _tbl.c.external_id,
                        _tbl.c.properties,
                    ).where(
                        and_(
                            _tbl.c.org_id == org_id,
                            _tbl.c.workspace_id == workspace_id,
                            _tbl.c.object_type == "Order",
                        )
                    )
                ).fetchall()

            # 从 Order properties 提取 memberId → createdAt
            member_orders: dict[str, list[datetime | None]] = {}
            for _ext_id, props in order_rows:
                props = props if isinstance(props, dict) else {}
                member_id = str(props.get("memberId") or "").strip()
                if not member_id or member_id not in member_ids:
                    continue
                created_at_str = props.get("createdAt")
                dt = None
                if created_at_str:
                    try:
                        dt = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass
                member_orders.setdefault(member_id, []).append(dt)

            result: dict[str, tuple[int, datetime | None]] = {}
            for mid, times in member_orders.items():
                valid_times = [t for t in times if t is not None]
                last = max(valid_times) if valid_times else None
                result[mid] = (len(times), last)
            return result

        except Exception:
            log.warning("link_aggregator_failed", exc_info=True)
            return {}

    return aggregator
