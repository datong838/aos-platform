# W5c5p ConfigurationStage 首事务 opt-in 围栏方案（2026-09-25）

上位 W5c5h–W5c5o；真实 DB 仍未迁移 `a0v_093/a0v_094`。`ConfigurationStageConsumer.run_once` 一次 `consumer_connection` 中完成 requested→succeeded/rejected 的短事务；`PostgresPendingPreparationDirectory` 只读路由，非状态推进；`RecoverableStoreAttempt` 的 heartbeat/settle 与未知结果/正式 attempt 关系复杂，应另波单列，不能混入本波。

## 文件级九步

1. 复习 Stage 精确四源授权、单事务嵌套 savepoint、`consumer_connection` 可选 guard 及原有 Stage 边界测试。
2. 本方案；仅 `configuration_stage_consumer.py` 的 `ConfigurationStageConsumer` 加可选精确 `OptInHostLease`，进入 process_one 前同事务 guard；新增 `test_a0v_w5c5p_stage_fence_pg.py` 与 verification。pending read-only 目录、RecoverableStoreAttempt、真实 DB/Host 不改。
3. 默认 None 原样。显式 opt-in 时 guard 失败整事务回滚，不可进入四源 authorize 或 requested 状态变更；错 tenant/token/epoch、过期 fail closed。仍不得把 Stage guard 当配置后续 Consumer 或外部 effect 的授权。
4. 隔离 PG 覆盖默认/有效 holder、未 acquire/错 epoch/过期/错租户拒绝，确认四源授权未被调用；保留旧边界测试。
5. W5c3–W5c5p 与 Host/定义/Stage 累计分组，记录 `AOS_DATABASE_URL` 测试隔离债；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 本波不处理 read-only pending 目录，也不触碰 RecoverableStoreAttempt 旧自然 attempt；不覆盖其它 Owner/三业务 worker/外部 effect。真实 Host flag 不启用，旧组关闭门不变。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5q：专门复审 RecoverableStoreAttempt heartbeat/settle 的精确租约与未知提交边界，再决定其 opt-in 围栏接线；旧 attempt 不重发。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
