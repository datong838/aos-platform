# W5c5p ConfigurationStage 首事务 opt-in 围栏核验（2026-09-25）

方案 `13cdfb20` 先行，实现 `ad5e7511`。真实 DB 未迁移 `a0v_093/a0v_094`，Host flag 未启用。

## 九步证据

1. 复习四源配置授权、Stage requested→succeeded/rejected 单事务及 `consumer_connection` 同事务 guard。
2. 仅 `configuration_stage_consumer.py` 加精确 `OptInHostLease` 可选入口；新增 `test_a0v_w5c5p_stage_fence_pg.py`。pending 只读目录和 RecoverableStoreAttempt 均不改。
3. 默认 None 原样；显式 opt-in 时在 `process_one_configuration_stage` 前同事务验证 scope/token/epoch/expiry，失败回滚并不进入四源授权或状态写入。
4. 隔离 PG 专项含旧 Stage 边界 **5 passed**；有效 holder、默认空请求、未 acquire、错 epoch、过期、错租户及错误 lease 类型均覆盖。空请求测试不证明真实配置提交。
5. 累计分组：W5c3–W5c5j 主组 **162 passed**，W5c5k–p 围栏组 **17 passed**，定义合同 **24 passed**；共 203 passed（另旧 Stage 边界 2 passed 与专项组中 3 passed 重叠）。首次 zsh 数组拼接、bash `mapfile` 编排错误未执行预定测试，修正后各组均通过。隔离 PG 已停；`git diff --check` 通过。旧 `AOS_DATABASE_URL` 夹具顺序债保留。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列。临时页与 Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格最早 2026-09-25 20:00:04.800482 UTC 后重审。真实 Host/worker/其它 Owner/外部 effect 未全链路围栏，不得执行旧组关闭或宣告 A0-V GREEN。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5q：复审 RecoverableStoreAttempt heartbeat/settle 精确租约及未知提交边界，先方案再决定最小接线；旧 attempt 不重发。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
