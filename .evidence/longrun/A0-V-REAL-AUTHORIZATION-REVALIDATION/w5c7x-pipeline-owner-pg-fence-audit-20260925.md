# W5c7x Pipeline Owner 隔离 PG fence 审计

新测试只在 session disposable `aos_test_*` 库创建每例唯一 probe 表，借用既有 `fence_case` 建立目录/运行角色与受管 assignment。`OptInHostLease.acquire` 和 `a0v_094` guard 都是真实隔离 PG SQL。仅三个 Owner 的 append/bind 业务回调被替换为同连接 probe INSERT，以便精确观察 fence-before-write、commit/rollback，而不构造真实来源/安装权威。

有效 lease 的 selection/control/bind 三次独立 `consumer_connection` 均在 exact tenant、`aos_runtime` 角色下提交；对测试 lease 注入旧 epoch 后三入口均报 `HostLeaseBlocked: HOST_LEASE_WORKER_FENCE_REJECTED`，回调未到达、probe 无行；有效 guard 后回调 INSERT 再异常，probe 回滚为空。说明 W5c7w 可选接口和现有事务钩子在隔离 PG 可组合，失配会 fail closed。

不能外推：三个真实 Owner 的发布/安装/权限/锁完整链在此测试被探针替换；未验证跨机器旧 Host 排他、生产 main 注入、业务 worker/Outbox/Occurrence/Store 多提交边界。真实库 `a0v_092` 无此 lease schema。下一波需从业务 worker 精确 unknown/Receipt 边界选一条独立方案，不因本测试启用真实 opt-in。
