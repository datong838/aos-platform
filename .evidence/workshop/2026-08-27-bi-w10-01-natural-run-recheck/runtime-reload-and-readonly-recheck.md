# BI-W10-01 自然运行修复加载与只读复核证据

- 证据截点：2026-08-27T18:51:02+08:00
- 租户：`org-org/dev-project`
- 代码：`aos-platform/m1@e1f22ecb`
- 修复提交：`4b0b457f`（已包含于当前代码）
- 新 API 进程启动：2026-08-27T18:48:58+08:00
- 操作边界：仅重载本机开发 API、GET 权威接口与执行合成测试；未手工运行 Pipeline，未重放 DLQ，未修改真实业务数据，未发布。

## 独立事实判定

1. 旧 API 进程启动于 2026-08-27T12:45:12+08:00，早于 `4b0b457f` 的 14:13:02+08:00 提交，因此自然运行失败时实际执行的是修复前代码。
2. 2026-08-27T18:48:58+08:00 重载后的 API 已从当前 `m1` 启动；启动日志确认 12 个真实错峰 Cron 已注册，唯一 Niushop SSH tunnel 建立成功。
3. 当前 SourceReadiness 仍是旧自然运行截点，整体 `failed`，其中 P02/P04/P06/P12 为 `ready`，其余 8 条为 `failed`；12 条 reconciliation 均为 `pass`。
4. P01/P03/P05/P08/P09/P10/P11 的最新 DLQ 均是重载前产生的 `STORE_CONFLICT / IDEMPOTENCY_CONFLICT`；P07 为独立的 MySQL 查询连接中断，不属于快照观测身份共因。
5. 修复加载后的下一批自然运行从上海时区 2026-08-28 02:00 的 P01 开始。只有新的自然 run、DLQ 与同截点 SourceReadiness 才能关闭运行事实；当前不得提前把 BI-W10-01 改判为 GREEN。

## 验证

- `GET /v1/health`：HTTP 200，`status=ok`
- `GET /v1/schedules`：12 条 enabled 计划，P01～P12 为上海时区每天 02:00～13:00 错峰
- `GET /v1/data/source-readiness`：4/12 ready，8/12 failed，12/12 reconciliation pass
- `test_ec_live_executor.py + test_ec_normalizer.py + test_qyh_cron_scheduler.py + test_source_readiness_source.py + test_source_readiness_service.py`：72 passed

## 下一步

保持修复后的本机 API 与自然 Cron worker 运行；从 P01 新 run 起只读逐项回收 run、DLQ、SourceReadiness，同一 source 若仍失败则只根据新的 exact error 做最小修复。禁止用旧 run、代码测试或 P12 单点成功替代 12 条同截点证据。
