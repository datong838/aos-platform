"""栖月汇真实 Cron 调度运行时。

计划定义仍存放在 ``meta_schedule``；每一次执行的权威记录存放在
``meta_schedule_run``。这避免了旧 UI 种子历史和 Phase5 进程内历史被误认
为真实同步证据。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.scheduling_engine import parse_cron_field
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.qyh-cron")

QYH_SCOPE = TenantScope("org-org", "dev-project")
QYH_PIPELINE_ORDER: tuple[tuple[str, str], ...] = (
    ("P01-shop-qyh", "店铺"),
    ("P02-product-qyh", "商品"),
    ("P03-product-sku-qyh", "商品SKU"),
    ("P04-category-qyh", "类目"),
    ("P05-order-qyh", "订单"),
    ("P06-order-line-qyh", "订单明细"),
    ("P07-shipment-qyh", "发货"),
    ("P08-customer-lite-qyh", "会员"),
    ("P09-weapp-qyh", "小程序"),
    ("P10-system-config-qyh", "系统配置"),
    ("P11-product-review-qyh", "商品评价"),
    ("P12-payment-qyh", "支付"),
)
# 开发期保持真实数据链路，但每个 OT 每天仅拉取一次，按小时错峰以避免集中拉取。
QYH_DAILY_CRON_BY_PIPELINE: dict[str, str] = {
    pipeline_id: f"0 {hour} * * *"
    for hour, (pipeline_id, _) in enumerate(QYH_PIPELINE_ORDER, start=2)
}
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_RUN_LOCK = threading.Lock()


def _row(item: Any) -> dict[str, Any]:
    return dict(item) if item is not None else {}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def cron_matches(cron: str, local_now: datetime) -> bool:
    """判断当前上海分钟是否命中五段 Cron；非法表达式一律不触发。"""
    parts = cron.strip().split()
    if len(parts) != 5:
        return False
    try:
        minute, hour, day, month, weekday = (
            parse_cron_field(parts[0], 0, 59),
            parse_cron_field(parts[1], 0, 23),
            parse_cron_field(parts[2], 1, 31),
            parse_cron_field(parts[3], 1, 12),
            parse_cron_field(parts[4], 0, 6),
        )
    except (TypeError, ValueError):
        return False
    cron_weekday = (local_now.weekday() + 1) % 7
    return (
        local_now.minute in minute
        and local_now.hour in hour
        and local_now.day in day
        and local_now.month in month
        and cron_weekday in weekday
    )


def next_run_at(cron: str, now: datetime | None = None) -> datetime | None:
    """用上海时区求下一次运行，最多扫描 370 天。"""
    from datetime import timedelta

    local = (now or datetime.now(_SHANGHAI)).astimezone(_SHANGHAI)
    candidate = local.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(370 * 24 * 60):
        if cron_matches(cron, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    return None


def _validate_cron_slot(
    scheduled_for: datetime,
    *,
    now: datetime | None = None,
) -> datetime:
    """只接受服务器当前 UTC 分钟，拒绝未来注入和历史补跑。"""
    if scheduled_for.tzinfo is None:
        raise ValueError("CRON_SLOT_TIMEZONE_REQUIRED")
    slot = scheduled_for.astimezone(timezone.utc).replace(second=0, microsecond=0)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(
        second=0,
        microsecond=0,
    )
    if slot != current:
        raise ValueError("CRON_SLOT_OUTSIDE_CURRENT_MINUTE")
    return slot


def ensure_qyh_staggered_daily_schedules() -> list[dict[str, Any]]:
    """把 12 OT 收敛为真实 live-pipeline 每日错峰 Cron，保留已有历史。"""
    from aos_api.phase5_pipeline_engine import get_engine

    engine = get_engine()
    unavailable = [
        pipeline_id for pipeline_id, _ in QYH_PIPELINE_ORDER
        if (
            (pipeline := engine.get_pipeline(QYH_SCOPE, pipeline_id)) is None
            or pipeline.execution_mode != "live"
            or pipeline.executor_id != "ec-live-v1"
        )
    ]
    if unavailable:
        raise RuntimeError("QYH_CRON_PIPELINE_UNAVAILABLE:" + ",".join(unavailable))

    items: list[dict[str, Any]] = []
    with connect(QYH_SCOPE) as conn:
        for pipeline_id, label in QYH_PIPELINE_ORDER:
            schedule_id = f"sch-{pipeline_id}"
            row = conn.execute(
                "SELECT last_run FROM meta_schedule WHERE id=%s AND org_id=%s AND project_id=%s",
                (schedule_id, *QYH_SCOPE.key),
            ).fetchone()
            last_run = row["last_run"] if row else None
            item = {
                "id": schedule_id,
                "cron": QYH_DAILY_CRON_BY_PIPELINE[pipeline_id],
                "pipelineId": pipeline_id,
                "enabled": True,
                "name": f"栖月汇-{label} 每天 {QYH_DAILY_CRON_BY_PIPELINE[pipeline_id].split()[1].zfill(2)}:00 同步",
                "ingest": {
                    "kind": "pipeline-live-v1",
                    "pipelineId": pipeline_id,
                    "sourceId": "niushop-qyh",
                },
                "lastRun": last_run,
                "orgId": QYH_SCOPE.org_id,
                "projectId": QYH_SCOPE.project_id,
            }
            conn.execute(
                """
                INSERT INTO meta_schedule
                  (id, cron, pipeline_id, enabled, name, ingest, last_run, org_id, project_id, props, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,'{}'::jsonb,NOW())
                ON CONFLICT (org_id, project_id, id) DO UPDATE SET
                  cron=EXCLUDED.cron, pipeline_id=EXCLUDED.pipeline_id, enabled=EXCLUDED.enabled,
                  name=EXCLUDED.name, ingest=EXCLUDED.ingest, updated_at=NOW()
                """,
                (
                    schedule_id, item["cron"], pipeline_id, True, item["name"],
                    _json(item["ingest"]), _json(last_run) if last_run is not None else None,
                    *QYH_SCOPE.key,
                ),
            )
            items.append(item)
        conn.commit()
    return items


def _get_schedule(scope: TenantScope, schedule_id: str) -> dict[str, Any] | None:
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT id, cron, pipeline_id, enabled, name, ingest, last_run FROM meta_schedule "
            "WHERE id=%s AND org_id=%s AND project_id=%s",
            (schedule_id, *scope.key),
        ).fetchone()
    if row is None:
        return None
    item = _row(row)
    return {
        "id": item["id"], "cron": item["cron"], "pipelineId": item["pipeline_id"],
        "enabled": item["enabled"], "name": item["name"], "ingest": item["ingest"],
        "lastRun": item["last_run"], "orgId": scope.org_id, "projectId": scope.project_id,
    }


def list_runs(scope: TenantScope, schedule_id: str, limit: int = 24) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    with connect(scope) as conn:
        rows = conn.execute(
            """SELECT id, scheduled_for, trigger, status, started_at, finished_at,
                      duration_ms, rows_written, error_code, error_message, executor_id
               FROM meta_schedule_run
               WHERE org_id=%s AND project_id=%s AND schedule_id=%s
               ORDER BY started_at DESC LIMIT %s""",
            (*scope.key, schedule_id, safe_limit),
        ).fetchall()
    return [
        {
            "id": row["id"], "scheduledFor": row["scheduled_for"], "trigger": row["trigger"],
            "status": row["status"], "startedAt": row["started_at"], "finishedAt": row["finished_at"],
            "durationMs": row["duration_ms"], "rowsWritten": row["rows_written"],
            "errorCode": row["error_code"], "errorMessage": row["error_message"],
            "executor": row["executor_id"],
        }
        for row in rows
    ]


def _claim_run(scope: TenantScope, schedule_id: str, scheduled_for: datetime, trigger: str) -> str | None:
    run_id = f"scr-{uuid.uuid4().hex[:16]}"
    with connect(scope) as conn:
        row = conn.execute(
            """INSERT INTO meta_schedule_run
                 (id, org_id, project_id, schedule_id, scheduled_for, trigger, status, started_at)
               VALUES (%s,%s,%s,%s,%s,%s,'running',NOW())
               ON CONFLICT (org_id, project_id, schedule_id, scheduled_for) DO NOTHING
               RETURNING id""",
            (run_id, *scope.key, schedule_id, scheduled_for.astimezone(timezone.utc), trigger),
        ).fetchone()
        conn.commit()
    return str(row["id"]) if row else None


def execute_schedule(
    scope: TenantScope,
    schedule_id: str,
    *,
    trigger: str,
    scheduled_for: datetime | None = None,
) -> dict[str, Any]:
    """执行一次真实 live pipeline，并把运行事实写入 PostgreSQL。"""
    schedule = _get_schedule(scope, schedule_id)
    if schedule is None:
        raise KeyError(schedule_id)
    if not schedule["enabled"]:
        raise ValueError("SCHEDULE_DISABLED")
    ingest = schedule.get("ingest") or {}
    if ingest.get("kind") != "pipeline-live-v1" or ingest.get("pipelineId") != schedule["pipelineId"]:
        raise ValueError("SCHEDULE_LIVE_BINDING_MISSING")

    slot = scheduled_for or datetime.now(timezone.utc)
    if trigger == "cron":
        slot = _validate_cron_slot(slot)
    run_id = _claim_run(scope, schedule_id, slot, trigger)
    if run_id is None:
        return {"status": "duplicate", "scheduleId": schedule_id, "scheduledFor": slot}

    started = time.monotonic()
    result: dict[str, Any]
    try:
        from aos_api.phase5_pipeline_engine import get_engine
        result = get_engine().execute_pipeline_once(scope, str(schedule["pipelineId"]))
    except Exception:  # fail closed and keep a durable error record
        result = {
            "ok": False, "rows_written": 0, "duration_ms": 0,
            "error_code": "SCHEDULE_EXECUTOR_EXCEPTION",
            "error_message": "schedule executor failed",
        }
    duration_ms = int(result.get("duration_ms") or max(1, (time.monotonic() - started) * 1000))
    status = "succeeded" if result.get("ok") else "failed"
    last_run = {
        "id": run_id, "at": datetime.now(timezone.utc).isoformat(), "status": status,
        "trigger": trigger, "rowsWritten": int(result.get("rows_written") or 0),
        "durationMs": duration_ms, "errorCode": str(result.get("error_code") or ""),
    }
    with connect(scope) as conn:
        conn.execute(
            """UPDATE meta_schedule_run SET status=%s, finished_at=NOW(), duration_ms=%s,
                   rows_written=%s, error_code=%s, error_message=%s, executor_id=%s
               WHERE id=%s AND org_id=%s AND project_id=%s""",
            (status, duration_ms, int(result.get("rows_written") or 0),
             str(result.get("error_code") or ""), str(result.get("error_message") or "")[:1000],
             "ec-live-v1", run_id, *scope.key),
        )
        conn.execute(
            "UPDATE meta_schedule SET last_run=%s::jsonb, updated_at=NOW() "
            "WHERE id=%s AND org_id=%s AND project_id=%s",
            (_json(last_run), schedule_id, *scope.key),
        )
        conn.commit()
    log.info("qyh_cron_run schedule=%s status=%s rows=%s trigger=%s", schedule_id, status, last_run["rowsWritten"], trigger)
    return {"id": run_id, "scheduleId": schedule_id, "status": status, "lastRun": last_run, "result": result}


def run_due_qyh(now: datetime | None = None) -> list[dict[str, Any]]:
    """Cron worker 单次 tick；只处理唯一栖月汇目标租户。"""
    local_now = (now or datetime.now(_SHANGHAI)).astimezone(_SHANGHAI)
    with _RUN_LOCK:
        with connect(QYH_SCOPE) as conn:
            rows = conn.execute(
                "SELECT id, cron FROM meta_schedule WHERE org_id=%s AND project_id=%s AND enabled=TRUE "
                "AND ingest->>'kind'='pipeline-live-v1' ORDER BY id",
                QYH_SCOPE.key,
            ).fetchall()
        outcomes: list[dict[str, Any]] = []
        for row in rows:
            if cron_matches(str(row["cron"]), local_now):
                outcomes.append(execute_schedule(QYH_SCOPE, str(row["id"]), trigger="cron", scheduled_for=local_now))
        return outcomes
