# W5c5n ConfigurationConsumer opt-in 事务围栏核验（2026-09-25）

上位 W5c5h–W5c5m，方案 `19b57c7f` 先行，实现 `710ae270`；真实库/Host/worker 未启用。

## 九步证据

1. 复习 ConfigurationConsumer 五段事务、begin/commit 的 drain/授权顺序、W5c5l 可选连接 guard 与 `a0v_094` 权限。
2. 仅 `configuration_consumer.py` 增可选 `OptInHostLease`/统一连接封装、新增 `test_a0v_w5c5n_configuration_fence_pg.py` 与本 verification；ConfigurationStage/disable/Host/真实库未改。
3. 默认 None 保持旧行为。opt-in 时 claim/current/begin/commit/ack 五次连接均独立执行 guard，写前校验同一事务 token/epoch/tenant；失权回滚，不能靠前次检查延续授权。
4. 隔离 PG 专项 **2 passed**：默认与有效 holder 空队列，未 acquire、错 epoch、过期、错租户在 delivery 入口拒绝，authorize/check_drained 未调用。专项未制造真实配置操作；五段连接复审及旧配置回归不能替代实际 opt-in 配置提交验收。
5. 累计主组 **318 passed、11 skipped**，W5c5k–n 隔离组 **12 passed**，定义合同独立 **24 passed**，合计 **354 passed、11 skipped、7 warnings**。跨模块 `AOS_DATABASE_URL` 测试夹具顺序债保留；隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”；`BROWSER_PARTIAL`。未保存、运行、冲刷队列；临时页/Vite 已关闭。
7. 实时只读门禁仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。真实库未应用 `a0v_093/a0v_094`，Host flag 未启用。ConfigurationStage/disable、Owner 主体、三业务 worker 与外部 effect 未全链路围栏；不能授权旧组关闭。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5o：RuntimeDisableConsumer 外层 claim/finish 与 executor 内独立事务分层围栏；不能将外层 guard 当 executor 授权。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
