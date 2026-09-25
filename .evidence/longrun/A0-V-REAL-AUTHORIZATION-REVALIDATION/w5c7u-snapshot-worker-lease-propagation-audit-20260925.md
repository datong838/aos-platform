# W5c7u Snapshot worker 可选 lease 传递审计

`PipelineControlServiceFactory.build_snapshot_worker` 现在只在显式传入 exact `OptInHostLease` 且 tenant scope 完全相同时，把**同一对象**传给 Schedule 与 saved Recovery runtime。省略时两个 runtime 仍为 `None`；工厂构造不 acquire、不连接数据库，也不调用 Store。既有下游事务 fence 代码未改。

生产 `services/aos-api/aos_api/main.py` 的 `_start_snapshot_group_worker` 仍以 `build_snapshot_worker(scope, store=store)` 调用，不传 lease；`scripts/a0v_ecommerce_runtime_host.py` 的 `--host-lease-opt-in` 也仍默认 false，且是另一 Host 启动路径。因此这只是独立 Schedule worker 的**显式接入接口**，没有上线 worker fence、没有 Host 排他、更没有全机 universe 或真实 closure 权限。

后续覆盖矩阵至少应检查：`main.py` cohosted/independent worker 的启动和停机、Host acquire/renew 生命周期；三个业务 worker 的连接/事务，`PipelineControlServices.approve_selection/approve_control/bind_schedule` Owner 写入；Schedule claim、original/completed/recovery、Single/Link/Retirement、Store 独立效果、Outbox/consumer/stage 等每个入口。任何未证明路径、旧未受管 Host 或外部 Store unknown 都保持 no-effect。真实 `a0v_093/094` 未迁移，不能简单打开 opt-in。
