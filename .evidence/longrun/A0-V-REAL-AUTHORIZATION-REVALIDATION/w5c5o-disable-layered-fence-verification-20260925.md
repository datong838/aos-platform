# W5c5o RuntimeDisable 分层 opt-in 事务围栏核验（2026-09-25）

上位 W5c5h–W5c5n，方案 `70d4a395` 先行，实现 `536ec84f`；真实库/Host/worker 未启用。

## 九步证据

1. 复习 RuntimeDisableConsumer 外层 claim/current/finish、RuntimeDisableExecutor 两阶段 begin/finish 独立事务和 W5c5k guard。
2. 仅 `disable_consumer.py`、`disable_executor.py` 增同一可选 `OptInHostLease`，新增 `test_a0v_w5c5o_disable_layered_fence_pg.py` 与本 verification；真实迁移/Host/其他 worker 未改。
3. 默认 None 保持旧路径。opt-in 时 Consumer 每次 `consumer_connection` 和 Executor 两次独立连接都在状态读写前调用同一租约 token/epoch guard；外层已过不等于内层获权，失权回滚。
4. 隔离 PG 专项 **2 passed**：有效 holder 可进入外层空 claim 与内层事务，错 epoch 对两层拒绝，未 acquire/过期/错租户拒绝，默认路径不调用 guard。专项未制造完整 disable 业务变更，不能当作 dependent/drain 效果验收。
5. 累计主组 **318 passed、11 skipped**，W5c5k–o 隔离组 **14 passed**，定义合同独立 **24 passed**，合计 **356 passed、11 skipped、7 warnings**；跨模块 `AOS_DATABASE_URL` 夹具顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”；`BROWSER_PARTIAL`。未保存、运行、冲刷队列；临时页/Vite 已关闭。
7. 实时只读门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。真实库未应用 `a0v_093/a0v_094`，Host flag 未启用。dependent 外部 effect、ConfigurationStage/Owner/三业务 worker 未全链路围栏；不能据此执行旧组关闭或宣告 A0-V GREEN。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5p：ConfigurationStage 与 pending/recovery 消费者逐事务围栏及故障注入，继续清查其余写路径。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
