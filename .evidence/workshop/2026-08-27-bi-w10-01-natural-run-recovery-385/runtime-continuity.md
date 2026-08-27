# BI-W10-01 Watchdog 恢复后运行连续性证据

- episode: `recovery-1787802622709`
- wake sequence: `385`
- 核验时间：2026-08-27T19:00～19:06+08:00
- 代码：`aos-platform/m1@a96b12e4`
- authority：`AOS-000376`
- 租户：`org-org/dev-project`
- 边界：GET-only 运行态回读与合成测试；未手工触发 Pipeline，未重放 DLQ，未修改真实数据，未发布。

## 独立核验

1. Git branch 为 `m1`；memory status/validate/gate 为 `GREEN_WITH_WARNINGS / GREEN / can_change_state=true`，所有强一致投影均 `CURRENT`。
2. `127.0.0.1:8080/v1/health` 返回 HTTP 200，`lsof` 回读监听 PID 61359。先前对 8000 的失败探针已纠正：8000 不是当前本地 API 入口。
3. `/v1/schedules` 返回 12 条 enabled 计划，覆盖 P01～P12，日调度为上海时区 02:00～13:00 错峰。
4. `/v1/data/source-readiness` 在 `2026-08-27T11:02:03.310687Z` 为 `failed`：P02/P04/P06/P12 ready，其余 8 条 failed，12 条 reconciliation 全部 pass。所有 latest run 仍是重载前自然批次。
5. `/v1/dlq` 共回读 58 条历史项；重载时刻 `2026-08-27T10:48:58Z` 之后新增 0。
6. `test_ec_live_executor.py`、`test_ec_normalizer.py`、`test_qyh_cron_scheduler.py`、`test_source_readiness_source.py`、`test_source_readiness_service.py` 同一集合连续两次退出码 0。本轮运行器吞掉 pytest 标准输出，因此不声称新的 passed 计数。

## 判定

`RUNTIME_CONTINUITY_RECOVERY_GREEN / NATURAL_CRON_EVIDENCE_PENDING / NO_RELEASE`

当前 API/Cron 运行连续性已独立核验，但修复加载后首个新自然 P01 周期尚未到达。正式 BI-W10-01 仍保持 pending；下一步只读回收新 run、DLQ 与同 cutoff SourceReadiness，遇到新失败则按 exact error 做最小修复。
