# W5c4x stalled Owner 隔离事务拒绝门核验（2026-09-25）

上位 231 A0-V、231-9 BG-00；计划 `w5c4x-stalled-owner-transaction-test-plan-20260925.md` 先行提交 `ec53cd97`，测试提交 `d0373b97`。本波没有真实或 fixture 成功关闭；只测隔离 PostgreSQL 的拒绝门。

## 九步执行

1. 复习正式 `a0v_091` SQL、`StalledSnapshotGroupClosureService`、测试库自动建/销流程、W5c4t 严格 24h 门。
2. 文件限本方案、`services/aos-api/tests/extension_runtime/test_a0v_w5c4x_stalled_owner_pg.py`、本 verification；未改 Owner/迁移/业务数据。
3. 新测试在 pytest 隔离库调用真实 SQL 函数：缺维护角色或 SERIALIZABLE→42501；正确非 superuser 维护会话但无 admin→42501；补当前 admin 而无原始 schedule claim→40001；拒绝后 closure Receipt=0。
4. 定向 **5 passed**。诊断过程发现默认隔离连接账号在外层非 superuser 门被拒，最初无法触及深层 claim 门；将**仅测试会话**切换现有 `aos_extension_maintainer` session authorization 后，精确读到 admin 与 claim 拒绝消息。未更改正式 SQL/角色授权。完整 12 Run 成功路径 fixture 尚未构造，不虚报覆盖。
5. 有界累计 W5c3/W5c4、定义/attempt/lease/preparation 等 **189 passed，7 warnings，20.65s**；隔离测试库已停止。此前更宽恢复 PG 集合中止事实不被覆盖。
6. 浏览器 5174 `/data/schedules` 只读复核 12 条计划和整组采集入口；页面不证明后台 rev4/事务门，`BROWSER_PARTIAL`。无运行、保存或队列冲刷，临时页/前端已关闭。
7. 方案一致性：拒绝侧 SQLSTATE 与零 Receipt 已证，成功侧/重放/回滚仍未证；不把隔离数据库测试当真实组关闭。实时只读资格仍 `STALLED_WAIT_24H`、`automaticAction=false`。
8. 本 verification 先落盘提交，随后 CAS 同步 AOS 上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c4y：构造完整 12 Run 隔离 fixture，验证成功关闭、保留 effect evidence、失败无半提交和同 key 重放；若真实组严格 24h 到线，仍需独立真实方案与全门禁再调用原 Owner。

当前原 12 Run running、定义 rev4 disabled；无商城源行读、旧代补跑、Host restart 或 push，A0-V/BG-00 未过、230 L0 挂起。
