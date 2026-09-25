# W5c8b Outbox ACK 丢响应双 Receipt 只读对账验证

## 结论

在一次性完整 PG 链中，`complete_a0v_050` 或 `reconcile_completed_a0v_050` 已提交后，即使调用方的成功响应不可用，独立 runtime 只读连接仍能以原租户、Outbox、attempt、lease token 与两份精确 Receipt 识别 `acked`。只读对账发生在后续 replay 调用之前；没有第二次 coordinator/source 调用作为对账条件。此结论仅适用于**已有已提交 ACK**；`unknown`/过期 `claimed` 且未具备双 Receipt 的原 attempt 仍冻结，不自动恢复或重发。

## 九步证据

1. 复习 231、A0-V/W5c8a、m1/AOS-000663、`a0v_050` SQL 与 W5c7y 原三个 Coordinator PG 红项。真实门禁 no authority。
2. 方案 `e1f9b3db` 先提交，限定测试 fixture 与独立 SELECT 对账；生产代码和真实 DB 不改。
3. 原 fixture 红项原因：基底单来源测试在 `ProductEventAnalysisService` 实例上覆盖 `_source_group`，遮蔽十二来源持久 locator；在 `data_case` 首次分析前撤掉实例假方法，保留生产强校验。随后发现测试重连使用 `conn.info.dsn` 丢失密码，改用一次性测试库 `AOS_DATABASE_URL` 并断言数据库名一致。只改两个测试文件，代码提交 `aca9b62b`。
4. 首轮重跑三个红例仍 3 errors（fixture 修正位置太晚）；前移后重跑 3 failed/525.31 秒，统一为 `fe_sendauth: no password supplied`。修复测试 DSN 后，ACK 独立单例 `1 passed, 7 warnings`（302.35 秒），其余 reconcile/生产工厂 `2 passed, 7 warnings`（567.67 秒）。这是三个正式绿例，历史红轮不抹除。
5. 近期 A0-V 短累计 `242 passed, 7 warnings`（36.14 秒）；完整 Coordinator 三例作为独立长测列示，不把它们重计为短累计。一次性 `aos_test_*` 库 0。
6. 内置浏览器 2026-09-25 19:51:58 CST 只读回读 A0-V rev4“已配置·已停用”及“数据组已停用”；待同步写队列 1 未冲刷。
7. 方案/SQL/测试复审：只读 SELECT 比较状态、原 attempt/token、两份 Ref；dev-org 会话不能读 org-org 行；已有 complete/reconcile 负例拒错 token/attempt/缺履行 Receipt。模拟的是提交后**响应不可用**，不是网络实际断线试验，也不授权调用方重试。未知状态恢复另立 W5c8c。
8. 本 verification 提交 m1 后更新 AOS CAS、Prime 强投影并回读；真实旧链不因隔离 PG GREEN 升级。
9. 自动进入 W5c8c：先设计原 attempt 的独立只读 Receipt 寻址和冻结恢复，不重入 coordinator 或自动新 claim。

真实 gate 同波只读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；全机 Host 拓扑、Fresh 单事务 Owner 与独立 plan/key 仍缺。24 小时阈值不自动授权。m1 单写不 push、230 L0 挂起、商城源行不读、dev-org 仅隔离 canary、旧 attempt 不重发/不手工 `run_definition`。
