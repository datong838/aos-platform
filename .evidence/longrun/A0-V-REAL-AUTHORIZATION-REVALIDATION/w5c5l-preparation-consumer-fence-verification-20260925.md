# W5c5l PreparationConsumer 首条 opt-in 写事务围栏核验（2026-09-25）

上位 W5c5h–W5c5k，方案 `82aeec9c` 先行，实现 `10331482`；真实库/Host/worker 未启用。

## 九步证据

1. 复习 `consumer_connection` 租户/角色/statement timeout、PreparationConsumer 的 claim/read/finish 分事务和 W5c5k `a0v_094` 原语。
2. 文件仅 `host_lease.py` 增事务内 fence 方法、`consumer_connection.py` 可选钩子、`preparation_consumer.py` claim/finish 显式 opt-in、新增 `test_a0v_w5c5l_preparation_fence_pg.py` 与本 verification；Host 启动器、其他 worker、真实迁移未改。
3. 默认 None 完全沿用旧连接行为；显式 `OptInHostLease` 且 scope 相同才可构造。claim/finish 在同一 runtime 事务、outbox 写前执行 `a0v_094`，失败回滚；token/epoch 不落日志/status。只读 `_read` 不在本波范围。
4. 隔离 PG 专项 **3 passed**：有效 holder 同事务通过且空队列 claim 正常，错 epoch 对 claim/finish 在写前拒绝，未 acquire 的 opt-in 拒绝，默认路径不调用 guard。首次 fixture import 未带入其依赖而报 setup 错，修正测试引用后通过。
5. 累计主组 **318 passed、11 skipped**，W5c5k+l 隔离组 **8 passed**，定义合同独立 **24 passed**，合计 **350 passed、11 skipped、7 warnings**；测试环境变量跨模块顺序债仍需治理。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”；`BROWSER_PARTIAL`。未保存、运行、冲刷队列；临时页/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。真实库尚无 `a0v_093/a0v_094`，Host flag 未启用。此波仅两段 outbox 写事务，PreparedJob 外部 effect、其他 consumer/worker、旧角色及全机拓扑均未围栏，不能授权真实关闭或 A0-V GREEN。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5m：Owner/配置/disable 相邻写事务逐项 opt-in 覆盖与过期故障注入；未全覆盖前继续默认关闭。

m1 单写不 push；旧 attempt 不补跑；商城源行不读；230 L0 挂起；dev-org 零 canary。
