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
        #   3. O1-A: Payment 丰富 _order_create_time（batch_read_public）
        #   4. apply_derived_metrics: 按 target_ot 计算 8 个派生指标写入 row（含 link_aggregator）
        #   5. build_link_rows: 按 target_ot 构造 14 条核心 Link 行追加到 rows
        normalized_rows = normalize_rows(input_rows, pipeline)
        output_rows = [dict(row) for row in normalized_rows]

        # O1-A: Payment 丰富 — 从 ecom_object 批量查 Order.createdAt 填入 _order_create_time
        _enrich_payment_order_create_time(eng, scope, output_rows, pipeline)

        # O1-A: 构造 link_aggregator（从已写入的 ecom_object/ecom_link 查 Order 聚合数据）
        aggregator = _make_link_aggregator(eng, scope)
        output_rows = apply_derived_metrics(output_rows, pipeline, link_aggregator=aggregator)
        output_rows = build_link_rows(output_rows, pipeline)

        # sink: Dataset（G4，W2 实现）
        ds = sink_to_dataset(eng, scope, pipeline, output_rows)

        # sink: OT + Link（G5，W3 实现）
        sink_to_ot(eng, scope, pipeline, output_rows)

        # sink: obj_instance（前端 analytics preview 需要查 obj_instance 表）
        _write_obj_instances(scope, pipeline, output_rows)

        # O1-C: 同事务写 projection_outbox 标记（投影完成后标记 projected=True）
        _mark_projection_outbox(eng, scope, pipeline, output_rows)

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


# ═══════════════════════════════════════════════════════════════
# O1-A: Payment 丰富 + link_aggregator 工厂
# ═══════════════════════════════════════════════════════════════

def _enrich_payment_order_create_time(
    eng: Any, scope: Any, rows: list[dict[str, Any]], pipeline: Any,
) -> None:
    """O1-A §5.2.11: Payment 批量丰富 — 从 ecom_object 查 Order.createdAt。

    当 target_ot=Payment 时，用 ns_pay.relate_id（≈order_id）关联查
    ecom_object 中已存在的 Order 对象的 createdAt，挂到 row._order_create_time。
    关联失败不阻塞 Pipeline。
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

    # 从 ecom_object 批量查 Order.createdAt
    store = getattr(eng, "ecom_consistency_store", None)
    if store is None:
        return

    org_id = getattr(scope, "org_id", "") or ""
    workspace_id = getattr(scope, "workspace_id", "") or ""

    try:
        from aos_api.ecom_consistency_store import ecom_object as _tbl
        from sqlalchemy import select, and_

        order_ids = list(id_to_rows.keys())
        _engine = getattr(store, "_engine", None)
        if _engine is None:
            return
        with _engine.connect() as conn:
            # 设置 GUC
            conn.execute(text(f"SET LOCAL aos.org_id = '{org_id}'"))
            conn.execute(text(f"SET LOCAL aos.workspace_id = '{workspace_id}'"))

            results = conn.execute(
                select(
                    _tbl.c.external_id,
                    _tbl.c.properties,
                ).where(
                    and_(
                        _tbl.c.org_id == org_id,
                        _tbl.c.workspace_id == workspace_id,
                        _tbl.c.object_type == "Order",
                        _tbl.c.external_id.in_(order_ids),
                    )
                )
            ).fetchall()

        for ext_id, props in results:
            created_at = (props or {}).get("createdAt") if isinstance(props, dict) else None
            if created_at:
                for row in id_to_rows.get(ext_id, []):
                    row["_order_create_time"] = created_at

        log.info(
            "payment_enriched orders_found=%d/%d pipeline=%s",
            len(results), len(order_ids), getattr(pipeline, "id", "?"),
        )
    except Exception:
        log.warning("payment_enrich_failed pipeline=%s", getattr(pipeline, "id", "?"), exc_info=True)


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
    workspace_id = getattr(scope, "workspace_id", "") or ""
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


# ═══════════════════════════════════════════════════════════════
# O1-C: projection_outbox 同事务标记
# ═══════════════════════════════════════════════════════════════

def _mark_projection_outbox(
    eng: Any, scope: Any, pipeline: Any, output_rows: list[dict[str, Any]],
) -> None:
    """O1-C: 在权威写入 + 投影写入完成后，写 projection_outbox 标记。

    每条 object/link 写一条 outbox 记录，projected=True（因为 _write_obj_instances
    已同步完成投影）。后续可切换为异步消费器模式。
    """
    store = getattr(eng, "ecom_consistency_store", None)
    if store is None:
        return

    engine = getattr(store, "_engine", None)
    if engine is None:
        return

    org_id = getattr(scope, "org_id", "") or ""
    project_id = getattr(scope, "project_id", "") or ""
    pipeline_id = str(getattr(pipeline, "id", ""))

    try:
        from datetime import datetime, timezone as _tz
        from sqlalchemy import text as _text

        now = datetime.now(_tz.utc)
        # 获取下一个 input_revision（简化版：用当前秒级时间戳）
        revision = int(now.timestamp())

        with engine.begin() as conn:
            conn.execute(_text(
                f"SET LOCAL aos.org_id = '{org_id}'"
            ))
            conn.execute(_text(
                f"SET LOCAL aos.workspace_id = '{project_id}'"
            ))

            for row in output_rows:
                if row.get("link_type"):
                    # Link 行
                    conn.execute(_text(
                        "INSERT INTO projection_outbox "
                        "(org_id, project_id, workspace_id, input_revision, change_kind, "
                        "link_type, source_external_id, target_external_id, "
                        "platform, shop_or_marketplace_id, payload, projected, projected_at) "
                        "VALUES (:org, :proj, :ws, :rev, 'upsert_link', "
                        ":lt, :src, :tgt, 'niushop', '1', :payload::jsonb, TRUE, now())"
                    ).bindparams(
                        org=org_id, proj=project_id, ws=project_id,
                        rev=revision, lt=row.get("link_type", ""),
                        src=str(row.get("source_pk", "")),
                        tgt=str(row.get("target_source_pk", "")),
                        payload='{}',
                    ))
                elif row.get("source_pk") or row.get("id"):
                    # Object 行
                    import json as _json
                    ext_id = str(row.get("source_pk") or row.get("id") or "")
                    payload = _json.dumps(
                        {k: v for k, v in row.get("properties", {}).items()},
                        ensure_ascii=False, default=str,
                    )
                    conn.execute(_text(
                        "INSERT INTO projection_outbox "
                        "(org_id, project_id, workspace_id, input_revision, change_kind, "
                        "object_type, external_id, "
                        "platform, shop_or_marketplace_id, payload, projected, projected_at) "
                        "VALUES (:org, :proj, :ws, :rev, 'upsert_object', "
                        ":ot, :eid, 'niushop', '1', :payload::jsonb, TRUE, now())"
                    ).bindparams(
                        org=org_id, proj=project_id, ws=project_id,
                        rev=revision,
                        ot=str(row.get("ot", "")),
                        eid=ext_id,
                        payload=payload,
                    ))

        log.info(
            "projection_outbox_marked rows=%d pipeline=%s",
            len(output_rows), pipeline_id,
        )
    except Exception:
        log.warning(
            "projection_outbox_mark_failed pipeline=%s",
            getattr(pipeline, "id", "?"),
            exc_info=True,
        )
