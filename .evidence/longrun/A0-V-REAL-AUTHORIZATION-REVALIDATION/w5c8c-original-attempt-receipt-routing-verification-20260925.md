# W5c8c 原 attempt 双 Receipt 只读寻址审计验证

## 结论

本波是代码、SQL 与既有隔离 PG 证据的只读审计，未修改生产代码或真实库。已提交 `acked` 可按原 tuple 和双 Receipt 独立核对；持久 `unknown` 有潜在幂等键寻址路径，但现有 `_replay_committed` 会调用 `_resume`，不是纯只读 resolver；过期 `claimed` 既不能按现有 SQL 合法转 `unknown`，也不能自动重领。两类未 ACK 原 attempt 继续冻结。审计矩阵见同目录 `w5c8c-original-attempt-receipt-routing-audit-20260925.md`。

## 九步证据

1. 对照 231、A0-V、m1/AOS-000664、W5c8a/b 和真实 gate；运行中服务/真实库尚未接入 W5c8a 严格 pending-only claim。
2. 方案 `50cf18ee` 先提交，限定本波审计与无真实副作用。
3. 完成三态矩阵：`acked` 精确回读；`unknown` 仅可研究原 Requirement 推导的持久键与双 Receipt；过期 `claimed` 缺合法状态迁移 authority。无 Receipt、多候选、租户/Run/来源/attempt 不符或提交不明均停。
4. 既有 route/Outbox/Receipt 不触源专项 `22 passed, 7 warnings`（33.16 秒）；未把该结果解释为生产恢复授权。
5. 近期短累计 `242 passed, 7 warnings`（36.47 秒）；不重计 W5c8b 的三条长例；一次性 `aos_test_*` 库 0。
6. 内置浏览器 2026-09-25 20:06:58 CST 只读回读 A0-V rev4“已配置·已停用”及“数据组已停用”；未点击写入或冲刷待同步队列。
7. 复审 `_HostAnalysisReceiptStore.read`、`read_exact`、`a0v_050` 双 Receipt 谓词、完成/对账 SQL。找到候选不等于唯一且可恢复；`_replay_committed` 会重入 `_resume`，不得用于只读对账；状态写入另设 authority。
8. 本 audit/verification 落盘提交 m1 后做 AOS CAS、Prime 强投影回读；真实旧链的 authority 不因此提升。
9. 自动进入 W5c8d：先方案后实现最小纯只读 resolver 及隔离 PG 负例；任何状态变更另设独立方案。

真实 gate 同波只读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`，缺全机 Host 拓扑、Fresh 单事务 Owner、独立 real closure plan/key。24 小时阈值本身不授权。m1 单写不 push、230 L0 挂起、商城源行不读、dev-org 仅隔离 canary、旧 attempt 不重发/不手工 `run_definition`。
