# W5c7w Pipeline Owner 可选 fence 审计

`PipelineControlServiceFactory.build(scope, host_lease=...)` 仅接受 exact `OptInHostLease` 与完全相同的 tenant scope；省略时原服务无 fence。显式注入时，`PipelineControlServices._approve` 的 selection/control 和 `bind_schedule` 均通过原 `consumer_connection` 的 `fence(conn, scope)` 钩子执行；该钩子位于租户/角色/超时设置后、Owner 写入前、同一数据库事务内。没有新增连接、commit 或缓存，测试证明同一连接对象上的 fence 先于三个 Owner 写调用。

`PipelineControlServiceFactory` 的其他 `build_*` 路径和生产 `main.py` 未传此参数；A0-V Runtime Host 亦未将 lease 传入工厂。真实库未迁移 `a0v_093/094`、Host flag 默认 off。此波仅补一个可选、隔离验证的接入点；不证明三业务 worker、Outbox/Occurrence、Store 跨事务，亦不证明全机 Host universe 或旧 Host 排他。失租并发与真正 PG Owner 回滚还需下一波专门验证，不以 mock 顺序测试替代。
