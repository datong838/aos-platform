# W5c6p 旧 Schedule 长时回归定位验证（2026-09-25）

## 第 1/9～4/9 步：方案与有界拆分

- W5c5t 上位复习后方案 `8fd8e72a` 先提交。明确候选三模块：`test_snapshot_schedule_runtime_pg.py` 7 项、`test_pipeline_snapshot_schedule_claim_pg.py` 9 项、`test_pipeline_snapshot_schedule_recovery_pg.py` 1 项，共 17 项；不把这组当成真实 A0-V 运行授权。
- 独立一次性 PG 中 runtime 首项 `test_claim_ack_and_input_ack_loss_recover_original_group_once` 在约 192 秒仍未终结，按 180 秒预算附近 SIGINT 中断，exit 2；它不计通过。中断栈在 `canonical_json.py`，期间 PG 会话持续查询推进；仅能判为高成本或卡滞未定，不能推定死锁或成功。
- 同一 runtime 其余 6 项 `6 passed, 1 deselected`（62.86 秒）；claim 模块 `9 passed`（13.09 秒），recovery 模块 `1 passed`（18.89 秒）。旧 17 项中 16 项独立通过，完整三模块组合仍不绿。本波无代码改动，未以改 fixture 掩盖超时。

## 第 5/9～7/9 步：累计、浏览器与风险复审

- W5c5k–z/W5c6a–m 加 JDBC 累计 `111 passed`，测试 PG 已停止。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`；页面还显示“暂未确认操作结果；请保留原幂等键核对，勿重复创建”和待同步写操作 1，均未操作/冲刷。该 UI 提示是未知边界，绝不重发。
- 真实门只读 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0，严格到线 UTC `2026-09-25T20:00:04.800482+00:00`。方案与实现一致：未知/超限不计绿，不触发真实 claim/Store/closure。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回；提交见 docs context57。
- 下一波 W5c6q：为唯一长时 runtime 用例单独做有界阶段计时/性能剖析，区分 fixture bootstrap、12 来源回放、canonical JSON 开销和等待；先方案/精确测试文件清单，再考虑最小改动。正式 closure 始终 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
