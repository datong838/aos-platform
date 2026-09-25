# W5c8f unknown 原源组纯只读路径停止验证

## 结论

计划中的旧路由包装因 PostgreSQL 只读事务与 `SELECT FOR SHARE` 不相容而在审计门停止；未新增生产代码、未调用 coordinator/source、未写 Outbox/真实库。停止原因与后继见同目录 `w5c8f-unknown-original-source-group-read-only-audit-20260925.md`。本波不声称原源组证据已完成。

## 九步证据

1. 复习 231/A0-V、W5c8d/e、AOS-000667、m1 和真实 gate。
2. 方案 `aac50735` 先提交；在触发停止条件后以 `4a99dffb` 明确 W5c8g 先改做无行锁历史源组读取。
3. 静态调用链 `read_unknown` → `_read` → `_accepted_occurrence_reference`，后者 `FOR SHARE OF o,a`；不满足严格 read-only 包装。未实现原定新模块。
4. 本地永久表零行复现：`transaction_read_only=on` + `SELECT 1 FROM public.meta_org WHERE FALSE FOR SHARE` 正式报 `psycopg.errors.ReadOnlySqlTransaction`；未读业务行。第一次轻量 DB 表不存在、第二次 TEMP TABLE 允许加锁均明确排除为正式判据。
5. 近期 Outbox/Worker/fleet 短累计 `107 passed, 7 warnings`（29.74 秒）；一次性 `aos_test_*` 库 0。测试 GREEN 不覆盖被停止的源组新功能。
6. 内置浏览器 2026-09-25 23:12:29 CST 只读回读 A0-V rev4“已配置·已停用”及“数据组已停用”；待同步写队列 1 未冲刷。
7. 复审确认不能改用可写连接伪装只读证据，也不能把业务 RunRef 当源 Run ID；须从原 Occurrence/Origin 单独寻址保存源组。
8. 本 audit/verification 落盘提交后更新 AOS CAS/Prime；本波记录为安全停止，不记为源组 GREEN。
9. 自动进入 W5c8g：先方案实现无行锁纯只读历史源组解析与隔离 PG；Host-fenced 对账仍在后继。

真实 gate 同波只读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；缺全机 Host 拓扑、Fresh 单事务 Owner、独立 real closure plan/key。230 L0 挂起、商城源行不读、dev-org 仅零 canary、旧 attempt 不重发/不手工 `run_definition`、m1 不 push。
