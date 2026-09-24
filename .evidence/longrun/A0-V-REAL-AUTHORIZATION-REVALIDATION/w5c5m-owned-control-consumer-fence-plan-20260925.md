# W5c5m OwnedControlConsumer opt-in outbox 写事务围栏方案（2026-09-25）

上位 W5c5h–W5c5l。真实库仍未迁移 `a0v_093/a0v_094`，Runtime Host flag 默认关闭。`OwnedControlConsumer` 负责 verify/enable delivery，`_claim` 与 `_finish` 通过 `consumer_connection` 写 outbox；中间的 `PreparedJob.verify/enable` 属于另一个 Owner/外部 effect 边界，不能由 outbox guard 替代。

## 文件级九步

1. 复习 OwnedControlConsumer、LiveInstallationOwner 构造传播、旧 PG/取消测试、W5c5l 连接可选 fence 与 `a0v_094` SQL。
2. 本方案；仅 `owned_control_consumer.py` 增同 scope 的可选 `OptInHostLease` 并在 claim/finish 传入 guard；新增 `test_a0v_w5c5m_owned_control_fence_pg.py` 与 verification。Host 启动器、PreparedJob、其他 consumer/worker 和真实 DB 不改。
3. 默认 None 保持旧行为。显式 opt-in 时，在同一 runtime 事务的 outbox claim/ack/retry 之前校验当前 token/epoch/租户；失权回滚，不从该 delivery 发起 verify/enable。`_read` 只读不改；未知外部结果不得重发。
4. 隔离 PG 覆盖有效 holder、未 acquire/错 epoch/过期拒绝、默认路径和取消安全；不得用 mock 替代真实函数的权限/锁证明。
5. W5c3–W5c5m 与 Host/定义/consumer 累计回归分组；如跨模块环境污染仍现，保留红灯并按稳定分组复测；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，禁止保存/运行/队列冲刷。
7. 此波只有 OwnedControlConsumer 的两个 outbox 写事务；PreparedJob.verify/enable、配置/disable/其他 worker、外部 effect 和全机拓扑仍未围栏。真实 Host 不启用，旧组关闭门仍不授权。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5n：配置与 disable consumer 的独立写事务逐项接线和故障注入；之后才评估 Owner 主体与三业务 worker。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
