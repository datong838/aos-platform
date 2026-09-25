# W5c8d 原 attempt 双 Receipt 纯只读 resolver 验证

## 结论与边界

`m1@f6c5b6cf` 增加未接线的 `OriginalAttemptReceiptResolver`，要求同租户 `aos_runtime`、只读事务、同一原 Outbox attempt/token、持久 RUNNING Analysis Receipt、唯一原 PREPARING Receipt、精确 fulfilled DataFulfillmentReceipt，并按原 Requirement/Run/Case/Occurrence 等字段核对。解析结果只是**诊断证据**，不写 Outbox、不调用 coordinator/source、不授予 `reconcile_completed` 或过期 `claimed` 状态迁移，也没有在真实服务上部署。完整源组/Host 围栏 authority 仍由后续独立门禁证明。

## 九步证据

1. 复习 231、A0-V、W5c8a/b/c、`a0v_050` 和 AOS-000665；真实 gate 未授权。
2. 方案 `61feb1ea` 先提交，`860c3b64` 在共享哈希键等价抽取前修订文件级清单。
3. 代码 `f6c5b6cf`：旧 Coordinator `_resume`/`_replay_committed` 与新 resolver 共用 `snapshot_route_key`，字节公式不变；新 resolver 仅 SELECT/read_exact，未接 Worker 自动路径。
4. 隔离 PG 历史红轮：第一轮写连接隔离级别不匹配，第二轮把仅在命令中存在的 `priorReceiptRef` 错当响应字段；修复后初始完整链 `1 passed`（287.84 秒），扩展负例 `1 passed`（271.98 秒），共享键重构后 `1 passed`（296.45 秒），最终补全缺 Analysis Receipt/错误 Requirement 后 `1 passed, 7 warnings`（293.70 秒）。最终用例覆盖 unknown、过期 claimed、读事务、dev-org 隔离、attempt/token/Requirement 漂移、缺 Analysis/Fulfillment Receipt、错误 Run、PREPARING 和多原始候选；source 调用计数保持 1。历史红轮不抹除。
5. 近期 Outbox/Worker/fleet 短累计 `107 passed, 7 warnings`（32.90 秒），不冒充上波 242 选择集；语法编译和 `git diff --check` 通过；一次性 `aos_test_*` 库 0。
6. 内置浏览器 2026-09-25 22:42:19 CST 只读回读 A0-V rev4“已配置·已停用”和“数据组已停用”；待同步写队列 1 未冲刷。
7. 代码/SQL/方案复审：新模块显式 SQL 仅 SELECT，连接强制 read-only；`read(key)` 后仍以 `read_exact` 与持久 key/target/request hash 校验唯一性，履行 Receipt 用原 Store 精确校验。原源组/Host 跨事务 authority 不由此证明；异常或不唯一均冻结，不把找到候选解释为可恢复。
8. 本 verification 提交后执行 AOS CAS/Prime 强投影回读，真实 gate 不随隔离 PG GREEN 自动升格。
9. 自动进入 W5c8e：先方案评估持久 `unknown` 原 tuple 的独立对账 authority，过期 `claimed` 状态迁移仍单独规划；当前绝不自动接线。

真实 gate 本波只读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`，缺全机 Host 拓扑、Fresh 单事务 Owner、独立 real closure plan/key。24 小时阈值本身不授权。m1 单写不 push、230 L0 挂起、商城源行不读、dev-org 仅零 canary、旧 attempt 不重发/不手工 `run_definition`。
