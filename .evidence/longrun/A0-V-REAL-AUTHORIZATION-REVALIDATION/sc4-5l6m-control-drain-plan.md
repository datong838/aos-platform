# SC4-5l6m 控制入口排空验证

Rules：m1 单写、先方案、真实 PG、自测后提交；不修改主库，不 push，230 L0 挂起。

基线 c2b528e8。本子项只验证控制入口的同步 Host 事务排空，不能替代安装级异步 attempt 排空。

现有 LockedEcommerceGrowthHostPort.commit 在执行前调用 a0v_028 锁函数（生产由 a0v_044 扩展到九/十项），锁保持到业务与回执事务结束。a0v_054 fence 的 FOR UPDATE 必须等待这些事务；不能提前写 fence Receipt。测试在隔离 schema 安装原 a0v_028、a0v_044，使用真实 aos_runtime 连接持有组锁，另一 maintainer 连接以 100ms lock_timeout 验证 fence 不能提交。释放原事务后，同 key fence 成功且仅一张回执。

修改文件：services/aos-api/tests/extension_runtime/test_event_control_dispatch_lifecycle_pg.py；不修改生产代码。退出：锁持有时确定性拒绝且组和回执不变，释放后可恢复；原生命周期回归通过。

下一项仍为 generation/occurrence 异步排空和 resumed disable/detach 组合测试，以及真实 Service 签名审批集成。
