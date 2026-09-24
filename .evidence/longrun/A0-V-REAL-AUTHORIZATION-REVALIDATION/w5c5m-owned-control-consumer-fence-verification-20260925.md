# W5c5m OwnedControlConsumer opt-in outbox 围栏核验（2026-09-25）

上位 W5c5h–W5c5l，方案 `44562c0f` 先行，实现 `d188aa0b`；真实库/Host/worker 未启用。

## 九步证据

1. 复习 OwnedControlConsumer 的 claim/read/finish、LiveInstallationOwner 构造边界、`consumer_connection` 和 `a0v_094` guard。
2. 仅 `owned_control_consumer.py` 增同 scope 显式 opt-in，在 claim/finish 调用原有可选 fence；新增 `test_a0v_w5c5m_owned_control_fence_pg.py` 与本 verification。PreparedJob/其他 consumer/Host/真实库未改。
3. 默认 None 保持旧行为；opt-in 时同一 runtime 事务在 outbox claim/ack/retry 前校验 token/epoch。拒绝即回滚，不从本 delivery 发起 verify/enable；只读 `_read` 未接入。
4. 隔离 PG 专项 **2 passed**：有效 holder 可进入空队列 claim，错 epoch 对 claim/finish 写前拒绝，未 acquire 拒绝，默认路径不调用 guard，租户错配构造被拒。初版测试“异租户”值与 fixture 同为 dev-org，修正为真正不同租户后通过。
5. 累计稳定分组 **318 passed、11 skipped**，W5c5k–m 隔离组 **10 passed**，定义合同独立 **24 passed**，合计 **352 passed、11 skipped、7 warnings**。跨模块 `AOS_DATABASE_URL` 夹具顺序债仍记录；隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”；`BROWSER_PARTIAL`。未保存、运行、冲刷队列；临时页/Vite 已关闭。
7. 实时只读门禁仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。真实库未应用 `a0v_093/a0v_094`，Host flag 未启用。本波不覆盖 PreparedJob.verify/enable、配置/disable、三业务 worker 或外部 effect；不具备全机排他、旧组关闭或 A0-V GREEN 权限。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5n：配置/disable consumer 写事务逐项 opt-in 与过期故障注入，继续默认关闭。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
