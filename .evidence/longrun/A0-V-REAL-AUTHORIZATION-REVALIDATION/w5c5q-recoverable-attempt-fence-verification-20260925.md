# W5c5q RecoverableStoreAttempt 心跳/收尾 opt-in 围栏核验（2026-09-25）

方案 `1195c8fb` 先行，实现 `7dd62f8f`。真实 DB 未迁移 `a0v_093/a0v_094`，Host flag 未启用；旧自然 attempt 不重发。

## 九步证据

1. 复习 `RecoverableStoreAttempt` 心跳、settle、取消/未知提交边界与 `consumer_connection` guard；claim 属于另一个更大上游事务。
2. 仅 `recoverable_store_attempt.py` 的 Owner/Attempt 加可选精确 `OptInHostLease` 与两笔独立事务 guard；新增 `test_a0v_w5c5q_recoverable_attempt_fence_pg.py`。`PipelineSnapshotGroupCompletion` 和真实 Host/DB 不改。
3. 默认 None 原样；opt-in 时心跳/settle 在各自事务入业务 Store 前验证当前 holder。失权后心跳停、收尾拒绝；未知心跳提交不自动重用 revision 或重发旧 attempt。此局部围栏不授权 claim/外部执行。
4. 隔离 PG 新专项 **3 passed**：默认/有效 holder 的心跳与 settle、未 acquire/错 epoch/过期/错租户/假 lease 拒绝，失败前不调用 Attempt Store；旧 unit 与新专项合并 **15 passed**。未执行真实 Store 提交。
5. 累计主组 **162 passed**、W5c5k–q 围栏组 **20 passed**、定义合同 **24 passed**，合计 **206 passed**。原 Attempt PG 合同独立 **17 skipped**（测试门槛未满足），不是绿色覆盖；跨模块 `AOS_DATABASE_URL` 夹具顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列；临时页/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0，严格线为 2026-09-25 20:00:04.800482 UTC 之后。claim 上游/其它 Owner/业务 worker/外部 effect 未全链路围栏，旧组关闭仍未授权。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5r：盘点 `PipelineSnapshotGroupCompletion` claim 上游及未围栏 Owner 写路径，先方案再按危险度拆波；不把本波局部覆盖误报为全链路安全。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
