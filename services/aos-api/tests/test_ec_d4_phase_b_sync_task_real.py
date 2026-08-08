"""D4 Phase B: SyncTask 真实执行 + Schedule 双记录 + 负向 + DLQ.

覆盖 G11~G14:
- G11 (真实执行): SyncTask.run 不再 mock (5000 硬编码) → rows/duration 真实.
- G12 (三向关联): Schedule.run → SyncRun 双记录 (按 pipeline_id 匹配).
- G13 (越租户隔离): scope-A 不可见 scope-B SyncTask/SyncRun.
- G14 (DLQ + PII 0 泄漏): 失败 SyncRun 有 error_code; 错误文本经 redact_sensitive
  (手机号等 PII 在 sanitized_summary 中 0 出现).

Fixture 复用 standard_pipeline_links 模式:
- 真实 PipelineEngine + DataSourceEngine (autouse reset)
- register_executor 注入测试执行器 (可控制成功/失败/重跑幂等)
- 注册 12 条 P01~P12 pipeline (实际只要 P01/P02 够覆盖, 但全注册保证三向关联)
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from aos_api.phase5_pipeline_engine import (
    get_engine as p5_get_engine,
    Pipeline,
    PipelineNode,
)
from aos_api.phase6_datasource_engine import (
    get_engine as p6_get_engine,
)
from aos_api.public_contracts import redact_sensitive
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org-b", "dev-project-b")
OTHER_SCOPE = TenantScope("dev-org-other", "dev-project-other")
NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)
TEST_EXECUTOR_ID = "d4-b-test-exec"

# P01~P12 最小管道清单 (仅用于注册 create_pipeline, graph 节点数可少)
PIPELINE_IDS: list[str] = [f"P{i:02d}" for i in range(1, 13)]
TARGET_OTS = [
    "Shop", "Product", "ProductSku", "Category",
    "Order", "OrderLine", "Shipment", "CustomerLite",
    "Weapp", "SystemConfig", "ProductReview", "Payment",
]


# ═══════════════════════════════════════════════
# 测试执行器 (支持: 状态位控制首次失败 / rows 数可控 / PII 报错样本)
# ═══════════════════════════════════════════════

class _TestExecutorController:
    """控制执行器行为 (供负向用)."""

    def __init__(self) -> None:
        self.force_fail_once: dict[str, int] = {}  # pipeline_id → 剩余 fail 次数
        self.fail_error_messages: dict[str, str] = {}  # 自定义错误消息
        self.rows_per_call: dict[str, int] = {}  # pipeline_id → 每次写入行数
        self.delay_ms_per_call: dict[str, int] = {}  # 模拟耗时

    def plan_fail(self, pipeline_id: str, times: int = 1, message: str = "") -> None:
        self.force_fail_once[pipeline_id] = times
        if message:
            self.fail_error_messages[pipeline_id] = message

    def set_rows(self, pipeline_id: str, n: int) -> None:
        self.rows_per_call[pipeline_id] = n

    def reset(self) -> None:
        self.force_fail_once.clear()
        self.fail_error_messages.clear()
        self.rows_per_call.clear()
        self.delay_ms_per_call.clear()


exec_controller = _TestExecutorController()


def _test_executor(pipeline: Any, nodes: list[Any], sample_input: dict[str, Any], **_kw: Any) -> dict[str, Any]:
    """注册到 P5 的执行器: 行为由 exec_controller 控制.

    返回: evidence dict — 与 PipelineEngine._evidence_from_result 的契约对齐.
    失败时直接 raise Exception, 由 _start_dispatch 捕获转为 failed evidence.
    """
    pid = getattr(pipeline, "id", "")
    # 模拟耗时
    delay_ms = exec_controller.delay_ms_per_call.get(pid, 10)
    if delay_ms:
        time.sleep(delay_ms / 1000.0)
    # 强制失败 (用于断点/冲突负向)
    remaining = exec_controller.force_fail_once.get(pid, 0)
    if remaining > 0:
        exec_controller.force_fail_once[pid] = remaining - 1
        custom = exec_controller.fail_error_messages.get(pid) or "Pipeline simulated failure"
        raise RuntimeError(custom)
    rows = exec_controller.rows_per_call.get(pid, 1)
    # 模拟 OT 写入: 每个 pipeline 写 rows 个对象
    output_rows = [
        {"id": f"{pid}-obj-{i}", "ts": NOW.isoformat()} for i in range(rows)
    ]
    return {
        "rows_read": rows,
        "rows_written": rows,
        "input_ref": f"dataset://catalog/src-{pid}",
        "output_ref": f"dataset://catalog/sink-{pid}",
        "lineage_ref": f"lineage://run/{pid}/src-to-sink",
        "quality_ref": f"quality://run/{pid}",
        "output_rows": output_rows,
    }


def _truthy_resolver(_ref: str) -> bool:
    """dataset/quality/object/artifact 通用解析器：测试中引用均合法。"""
    return True


def _lineage_resolver(_ref: str) -> bool:
    """lineage:// 引用解析器。"""
    return True


# ═══════════════════════════════════════════════
# fixtures
# ═══════════════════════════════════════════════


def _seed_pipelines_and_executor() -> dict[str, Pipeline]:
    """在 TEST_SCOPE 下注册 P01~P12 管道 + 绑定测试执行器.

    返回 pipeline_id → Pipeline dict.
    """
    from aos_api.lineage_graph import get_graph as _get_lineage_graph

    eng = p5_get_engine()
    # 注册执行器 / resolver (每个测试 reset 后重新注册)
    eng.register_executor(TEST_EXECUTOR_ID, _test_executor)
    eng.register_evidence_resolver("dataset", _truthy_resolver)
    eng.register_evidence_resolver("artifact", _truthy_resolver)
    eng.register_evidence_resolver("object", _truthy_resolver)
    eng.register_evidence_resolver("lineage", _lineage_resolver)
    eng.register_evidence_resolver("quality", _truthy_resolver)

    # 清理 lineage 图
    lg = _get_lineage_graph()
    lg._nodes.clear()

    registered: dict[str, Pipeline] = {}
    for pid, ot in zip(PIPELINE_IDS, TARGET_OTS):
        pl = eng.create_pipeline(
            TEST_SCOPE,
            f"{pid} {ot} 管道",
            pipeline_type="ETL",
            write_mode="SNAPSHOT",
            execution_mode="live",
            executor_id=TEST_EXECUTOR_ID,
            execution_timeout_seconds=10.0,
            id=pid,  # 显式指定 Pipeline.id == "P01", 保证 get_pipeline(scope, "P01") 能命中
        )
        # 最小 3 节点: source→transform→sink
        n1 = eng.add_node(TEST_SCOPE, pl.id, "Source", node_type="source")
        n2 = eng.add_node(TEST_SCOPE, pl.id, "Normalize", node_type="transform")
        n3 = eng.add_node(TEST_SCOPE, pl.id, "Sink", node_type="sink")
        eng.add_edge(TEST_SCOPE, pl.id, n1.id, n2.id)
        eng.add_edge(TEST_SCOPE, pl.id, n2.id, n3.id)
        registered[pid] = pl
    return registered


@pytest.fixture(autouse=True)
def _reset_between():
    """每个用例前后清空 P5 / P6 单例 + 重置执行器控制."""
    from aos_api.lineage_graph import get_graph as _get_lineage_graph

    p5 = p5_get_engine()
    p6 = p6_get_engine()
    p5.reset_all_for_tests()
    p6.reset()
    lg = _get_lineage_graph()
    lg._nodes.clear()
    exec_controller.reset()
    yield
    p5.reset_all_for_tests()
    p6.reset()
    lg._nodes.clear()
    exec_controller.reset()


# ═══════════════════════════════════════════════
# B1 · SyncTask 真实执行 (G11)
# ═══════════════════════════════════════════════


class TestB1RunSyncReal:
    """Phase B1: run_sync_task → execute_pipeline_once → 真实 rows/duration/status."""

    def test_rows_not_hardcoded_5000_and_positive(self):
        _seed_pipelines_and_executor()
        # 控制 P01 写 3 rows
        exec_controller.set_rows("P01", 3)
        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B1 P01 Real Sync",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P01"},
        )
        run = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
        # G11-a: 不再是 mock 的 5000
        assert run.rows_synced != 5000, f"mock 5000 未移除, 实际 rows={run.rows_synced}"
        # G11-b: 与 executor.set_rows(3) 对齐
        assert run.rows_synced == 3, f"真实执行应返回 rows=3, 实际={run.rows_synced}"
        # G11-c: status 三态
        assert run.status == "success", f"期望 success, 实际={run.status}"
        # G11-d: duration_ms > 0 且 ≈ 真实耗时 (executor delay=10ms, 设>1ms)
        assert 1 <= run.duration_ms < 60_000, (
            f"duration 异常: {run.duration_ms}ms, 应在 (1ms, 60s)"
        )
        # G11-e: 有 pipeline_id 追踪
        assert run.pipeline_id == "P01"
        # G11-f: finished_at > started_at (真实推进)
        assert run.finished_at >= run.started_at

    def test_status_failed_when_pipeline_missing(self):
        _seed_pipelines_and_executor()
        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B1 Missing Pipeline",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "PX_NO_EXIST"},
        )
        run = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
        assert run.status == "failed", f"管道不存在应 failed, 实际={run.status}"
        assert run.error_code == "PIPELINE_NOT_FOUND", (
            f"期望 error_code=PIPELINE_NOT_FOUND, 实际={run.error_code}"
        )
        assert run.rows_synced == 0
        # SyncTask.status 同步变为 error
        updated = p6.get_sync_task(sync.id, scope=TEST_SCOPE)
        assert updated.status == "error", f"失败应同步 SyncTask.status=error"


# ═══════════════════════════════════════════════
# B2 · Schedule → SyncTask 双记录 (G12 三向关联)
# ═══════════════════════════════════════════════


class TestB2ScheduleSyncDoubleRecord:
    """B2: Schedule.run_schedule 成功后, 按 pipeline_id 松散匹配写 SyncRun."""

    def test_run_schedule_writes_syncrun_when_matching_pipeline_id(self):
        pipedict = _seed_pipelines_and_executor()
        exec_controller.set_rows("P02", 7)

        p5 = p5_get_engine()
        p6 = p6_get_engine()
        # 注册 SyncTask (同 scope, config.pipeline_id=P02)
        sync = p6.create_sync_task(
            name="B2 P02 Sync",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P02"},
        )
        # 注册 Schedule (绑定 P02)
        sc = p5.create_schedule(
            TEST_SCOPE,
            name="P02 cron",
            cron_expr="0 * * * *",
            pipeline_id="P02",
        )
        # 跑一次 schedule
        sr = p5.run_schedule(TEST_SCOPE, sc.id)
        assert sr.status == "succeeded", f"Schedule.run 应 succeeded, 实际={sr.status}"
        # G12-a: 同 pipeline_id 的 SyncTask 下出现 SyncRun (不一定 run.id==sr.id, 按行数判断)
        runs = p6.list_sync_runs(sync.id, scope=TEST_SCOPE)
        assert len(runs) == 1, (
            f"run_schedule 后应该给匹配的 SyncTask 追加 1 条 SyncRun, 实际 {len(runs)}"
        )
        r0 = runs[0]
        assert r0.pipeline_id == "P02"
        assert r0.status == "success"
        assert r0.rows_synced == 7, f"SyncRun.rows 应匹配执行器 7, 实际 {r0.rows_synced}"

    def test_no_syncrun_when_no_matching_pipeline_id(self):
        pipedict = _seed_pipelines_and_executor()
        exec_controller.set_rows("P03", 5)

        p5 = p5_get_engine()
        p6 = p6_get_engine()
        # SyncTask 绑定 P02 但 schedule 是 P03 → 不匹配
        sync_p02 = p6.create_sync_task(
            name="B2 Unmatched P02",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P02"},
        )
        sc = p5.create_schedule(
            TEST_SCOPE,
            name="P03 cron",
            cron_expr="0 * * * *",
            pipeline_id="P03",
        )
        sr = p5.run_schedule(TEST_SCOPE, sc.id)
        assert sr.status == "succeeded"
        runs = p6.list_sync_runs(sync_p02.id, scope=TEST_SCOPE)
        assert len(runs) == 0, (
            "pipeline_id 不匹配时不应写 SyncRun"
        )


# ═══════════════════════════════════════════════
# B3 · cron 调度累积 (G12 1h 频率 3 次)
# ═══════════════════════════════════════════════


class TestB3CronAccumulation:
    """B3: 连续 3 次 run_schedule → ScheduleRun/SyncRun 3 条一致, 数据不重复不遗漏."""

    def test_3_runs_cron_consistency(self):
        pipedict = _seed_pipelines_and_executor()
        # 每次 P05 写不同 rows (3 / 5 / 2) 共 10
        p5 = p5_get_engine()
        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B3 P05 Cron Sync",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P05"},
        )
        sc = p5.create_schedule(
            TEST_SCOPE,
            name="P05 hourly cron",
            cron_expr="0 * * * *",
            pipeline_id="P05",
        )
        expected_rows_sequence = [3, 5, 2]
        schedule_runs: list[Any] = []
        for expected in expected_rows_sequence:
            exec_controller.set_rows("P05", expected)
            sr = p5.run_schedule(TEST_SCOPE, sc.id)
            schedule_runs.append(sr)
        # 3 条 ScheduleRun 全成功
        assert all(s.status == "succeeded" for s in schedule_runs), (
            f"3 次 schedule 应全 succeeded, 实际 status={[s.status for s in schedule_runs]}"
        )
        # SyncRun 也 3 条, 顺序一致
        sync_runs = p6.list_sync_runs(sync.id, scope=TEST_SCOPE)
        assert len(sync_runs) == 3, f"SyncRun 数量应 3, 实际 {len(sync_runs)}"
        # 排 started_at 升序
        sync_runs_sorted = sorted(sync_runs, key=lambda r: r.started_at)
        actual_rows = [r.rows_synced for r in sync_runs_sorted]
        assert actual_rows == expected_rows_sequence, (
            f"rows 序列应 {expected_rows_sequence}, 实际 {actual_rows}"
        )
        # 3 条 ScheduleRun 总和: 3+5+2=10 (可追溯不重复不遗漏 — 因为每次 set_rows 都是新值, 故不重复)
        total_sync = sum(actual_rows)
        assert total_sync == 10, f"3 次累积 rows=10, 实际 {total_sync}"


# ═══════════════════════════════════════════════
# B4 · 负向 4 段 + DLQ PII 脱敏 (G13/G14)
# ═══════════════════════════════════════════════


class TestB4NegativeAndDLQ:
    """4 段负向 (重跑幂等/断点/冲突/越租户) + G14 PII 0 泄漏."""

    # ── 重跑幂等 ──
    def test_repeat_runs_same_checkpoint_no_duplicates(self):
        """重跑幂等: 同一 SyncTask 连续跑 2 次, executor 都写同一份 3 行,
        rows_synced 应各自=3 (不重复数据, 即 SyncRun 单条 rows 不翻倍)."""
        _seed_pipelines_and_executor()
        exec_controller.set_rows("P04", 3)
        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B4 Idempotent P04",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P04"},
        )
        r1 = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
        r2 = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
        assert r1.status == "success" and r2.status == "success"
        # G14-重跑: 两次 run 独立, 各自 rows=3 (不重复 = 两条独立记录, 单条 rows 不再 6/9)
        assert r1.rows_synced == 3, f"r1 行应为 3, 实际 {r1.rows_synced}"
        assert r2.rows_synced == 3, f"r2 行应为 3, 实际 {r2.rows_synced}"

    # ── 断点 (第一次失败 → DLQ 记录 → 第二次成功) ──
    def test_breakpoint_and_dlq_record(self):
        _seed_pipelines_and_executor()
        # 样本含 PII: 手机号 + email
        pii_message = (
            "用户 138-0000-0000 订单失败, 联系邮箱 admin@example.com "
            "含身份证 110101199001011234 密码 abc123"
        )
        exec_controller.plan_fail("P06", times=1, message=pii_message)
        exec_controller.set_rows("P06", 4)

        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B4 Breakpoint P06",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P06"},
        )
        r_fail = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
        # B4-断点-1: 第一次失败
        assert r_fail.status == "failed", f"第一次应 failed, 实际 {r_fail.status}"
        assert r_fail.error_code != "", f"失败应带 error_code, 实际空"
        # G14-DLQ: SyncRun 视为 DLQ 记录 (DLQ 方案 A). 失败条数 +1
        all_runs = p6.list_sync_runs(sync.id, scope=TEST_SCOPE)
        failed_records = [r for r in all_runs if r.status == "failed"]
        assert len(failed_records) >= 1, "DLQ 记录至少 1 条失败"
        # G14-PII 0 泄漏: sanitized_summary (SyncRun.error) 不应含原始手机号/身份证/密码
        summary = r_fail.error or ""
        for needle in ["138-0000-0000", "110101199001011234", "abc123", "admin@example.com"]:
            assert needle not in summary, (
                f"DLQ sanitized_summary 泄漏 PII: 原文 '{needle}' "
                f"出现在 summary={summary!r}"
            )
        # 第二次成功
        r_success = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
        assert r_success.status == "success", f"重跑应 success, 实际 {r_success.status}"
        assert r_success.rows_synced == 4, f"重跑后 rows=4, 实际 {r_success.rows_synced}"
        # 总共至少 2 条: 1 failed (DLQ) + 1 success
        assert len(all_runs) >= 2 or len(p6.list_sync_runs(sync.id, scope=TEST_SCOPE)) >= 2

    # ── 冲突 (并发 run_sync_task 同一 SyncTask) ──
    def test_concurrent_run_conflict_handling(self):
        """冲突: 2 线程并行跑同一 SyncTask, 预期至少 1 条 success,
        不出现 'running' 挂死 (当前实现不做 CAS 拒绝, 但要求 2 条都能终态)."""
        _seed_pipelines_and_executor()
        exec_controller.set_rows("P07", 2)
        # 加入 40ms 延迟, 放大并发窗口
        exec_controller.delay_ms_per_call["P07"] = 40
        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B4 Conflict P07",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P07"},
        )
        results: list[Any] = []
        lock = threading.Lock()

        def _worker():
            r = p6.run_sync_task(sync.id, scope=TEST_SCOPE)
            with lock:
                results.append(r)

        t1 = threading.Thread(target=_worker)
        t2 = threading.Thread(target=_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        # 2 条结果, 无 running 挂死
        assert len(results) == 2, f"2 线程应返回 2 条结果, 实际 {len(results)}"
        for r in results:
            assert r.status in {"success", "failed"}, (
                f"终态应 success/failed, 实际={r.status}"
            )
        # 至少 1 条 success
        assert any(r.status == "success" for r in results), "应有 ≥1 条 success"

    # ── 越租户隔离 (G13) ──
    def test_cross_scope_isolation(self):
        """G13: TEST_SCOPE 创建的 SyncTask → OTHER_SCOPE 查不到;
        OTHER_SCOPE 调 run_sync_task → 不存在 (抛 KeyError 或失败)."""
        _seed_pipelines_and_executor()
        p6 = p6_get_engine()
        sync = p6.create_sync_task(
            name="B4 Isolation P08",
            source_id="src-weimall",
            scope=TEST_SCOPE,
            config={"pipeline_id": "P08"},
        )
        # G13-a: TEST_SCOPE 能看到, OTHER_SCOPE list 看不到
        in_scope, _ = p6.list_sync_tasks(scope=TEST_SCOPE)
        out_scope, _ = p6.list_sync_tasks(scope=OTHER_SCOPE)
        assert any(s.id == sync.id for s in in_scope), "同 scope 应可见"
        assert not any(s.id == sync.id for s in out_scope), "越 scope 应不可见"

        # G13-b: OTHER_SCOPE 通过 sync.id 调用 get_sync_task 应 None
        from_other = p6.get_sync_task(sync.id, scope=OTHER_SCOPE)
        assert from_other is None, "越 scope get_sync_task 应返回 None"

        # G13-c: OTHER_SCOPE.run_sync_task(sync.id) → KeyError or failed (因为找不到)
        with pytest.raises(KeyError):
            p6.run_sync_task(sync.id, scope=OTHER_SCOPE)


# ═══════════════════════════════════════════════
# 退出门 G11~G14 汇总 (一个 assert 清单, 便于验收时一次性看总分)
# ═══════════════════════════════════════════════


class TestPhaseBGates:
    """每个 Gate 对应一个微型测试, 结果以单断言呈现."""

    def test_G11_sync_run_real_execution(self):
        TestB1RunSyncReal().test_rows_not_hardcoded_5000_and_positive()

    def test_G12_schedule_sync_double_record(self):
        TestB2ScheduleSyncDoubleRecord().test_run_schedule_writes_syncrun_when_matching_pipeline_id()

    def test_G13_cross_scope_isolation(self):
        TestB4NegativeAndDLQ().test_cross_scope_isolation()

    def test_G14_dlq_pii_zero_leak_and_breakpoint(self):
        TestB4NegativeAndDLQ().test_breakpoint_and_dlq_record()

    def test_G14_idempotent_rerun(self):
        TestB4NegativeAndDLQ().test_repeat_runs_same_checkpoint_no_duplicates()

    def test_G14_concurrent_conflict_no_stall(self):
        TestB4NegativeAndDLQ().test_concurrent_run_conflict_handling()
