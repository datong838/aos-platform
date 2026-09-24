# W5c5l PreparationConsumer 首条 opt-in 写事务围栏方案（2026-09-25）

上位 W5c5h–W5c5k；真实库仍 `a0v_092`，`a0v_093/a0v_094` 只在隔离 PG 验证。`PreparationConsumer` 的 `_claim` 与 `_finish` 均通过 `consumer_connection` 独立事务写 outbox，`_read` 为只读；中间 `PreparedJob` 可涉及外部 effect，不能因这两次写围栏就宣称全链路安全。

## 文件级九步

1. 复习 `consumer_connection` 精确 runtime 角色/tenant/10s statement timeout、`PreparationConsumer` 三段事务与测试，以及 W5c5k guard 函数权限。
2. 最小文件清单：本方案；`host_lease.py` 增加进程内 token/epoch 的事务内 guard 方法；`consumer_connection.py` 增加可选 fence 钩子（默认 None）；`preparation_consumer.py` 仅 `_claim/_finish` 传入显式 opt-in lease；新增专项测试与 verification。Host 启动器、其他 consumer/worker、真实迁移/库不改。
3. 默认不传租约保持原行为。显式 opt-in 时，同一 runtime 事务在 outbox claim/ack/retry **之前**调用 `a0v_094`，校验同一 tenant、token/epoch；失败整事务回滚、不得发起 PreparedJob。`_finish` 失败后不自动重试未知结果，交原有 outbox/Receipt 对账。token 不进入日志/status。
4. 隔离 PG 测有效 guard、失权/错 epoch 回滚、无租约 fail closed、旧路径不调用函数；专项审查 cancellation/外部 effect 间隙。
5. 累计 W5c3–W5c5l 与 Host/定义/消费者相关回归分组执行，记录环境变量顺序债；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled；不点击写操作。
7. 只覆盖 PreparationConsumer 两个 outbox 写事务；`_read`、PreparedJob、其他消费者/三业务 worker、外部 effect 均未获全链路 fencing，真实 Host 不启用。真实关闭仍受严格 24h、全机拓扑、单次 Owner/独立审计门约束。
8. verification 提交后 CAS 更新 docs/AOS 项目上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c5m：Owner/配置/disable 等相邻写事务逐项覆盖与过期边界测试；未全覆盖前继续默认关闭。

m1 单写不 push；旧 attempt 不补跑；商城源行不读；230 L0 挂起；dev-org 零 canary。
