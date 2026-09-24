# W5c5n ConfigurationConsumer opt-in 写事务围栏方案（2026-09-25）

上位 W5c5h–W5c5m；真实库 `a0v_092`，新租约迁移只在隔离 PG。`ConfigurationConsumer.run_once` 有 claim、current read、begin fence、commit configuration、ack/retry 五个独立 `consumer_connection`，其中四段可写；`ConfigurationStageConsumer` 与 RuntimeDisableConsumer 是不同执行边界，留后续波。

## 文件级九步

1. 复习 ConfigurationConsumer 五段事务、begin/commit 的现有 drain/授权顺序、W5c5l 可选 fence、旧 PG 测试。
2. 本方案；仅 `configuration_consumer.py` 增构造时可选精确 scope 的 `OptInHostLease`，统一连接封装确保所有写事务先 guard；新增 `test_a0v_w5c5n_configuration_fence_pg.py` 与 verification。真实迁移/Host/其他 worker 不改。
3. 默认 None 沿用原路径。opt-in 时每次连接在 scope/角色/timeout 已设之后、claim/begin/commit/ack 任何写入前执行 `a0v_094`；错 token、旧 epoch、过期/漂移回滚，不进入 drain。current read 可一并 guard，但不据此宣称跨事务连续授权；每个写事务须独立检查。
4. 隔离 PG 覆盖有效 holder、未 acquire/错 epoch、默认路径、断言失权时 authorize/check_drained 不调用；不伪造真实关闭权。
5. W5c3–W5c5n 与 Host/定义/配置累计分组回归，保留测试环境顺序债；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled；不保存/运行/冲刷队列。
7. 只覆盖 ConfigurationConsumer；ConfigurationStageConsumer、RuntimeDisableConsumer、PreparedJob、三业务 worker 及外部 effect 未覆盖。真实库未迁移，flag 不启用；全机拓扑与严格 24h/正式 Owner 关闭门不变。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5o：RuntimeDisableConsumer 的 claim/finish 与 executor 内独立事务分层围栏，不把外层 guard 当 executor 授权。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
