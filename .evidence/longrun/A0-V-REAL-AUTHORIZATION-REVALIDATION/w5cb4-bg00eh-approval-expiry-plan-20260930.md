# W5CB4 BG00EH｜网络批准预检等待后的时效

基线 m1@27c38634 / AOS-000996。复习 231-1 唯一权威、231-3 提交末尾复验、BG00EE 消费设计与 BG00EG 核查结论。`precheck_network_activation` 只在 Proposal 读取后采样一次时间；随后 Approval/成员/依赖锁等待可跨过 Proposal 或 Approval 到期时间。

## 文件与验证

- 新增 `services/aos-api/tests/aip/test_network_approval_precheck_expiry_pg.py`：使用 pytest 自动创建的 disposable PG，正式 Producer/Guard/Store 代码创建合成的隔离 Proposal/Event。测试独立 issuer 只在测试连接用 session authorization 模拟数据库角色，不能作为正式身份验收。独立连接锁住 checker membership；工作线程实际执行预检；观察 pg_stat_activity 的 Lock 等待后等待真实数据库时钟跨过期限，再释放。覆盖 Proposal 到期、Approval 到期、未到期正向与零 NetworkPolicy 写入。
- 修改 `services/aos-api/aos_api/aip_network_policy_approval_consumer.py`：仅在上述 RED 成立时，在所有现有检查后、返回 Precheck 前再次取 DB clock_timestamp，按已有错误类型拒绝过期 Proposal/Event。没有新增激活、角色或数据库迁移。
- 新增本波 verification：记录真实锁等待、RED/GREEN和相邻回归。现有历史 a0v117 克隆测试不能冒充 a0v118 正式批准；不为其绕过118签发门。

事务内模拟夹具只在名称匹配 aos_test_*_ti4_test 的测试库；禁止共享数据库开关。默认测试自动清理其自身新建库，不接触当前权威库/备份。测试不调用 Provider/商城，也不创建 Run。

退出条件：入口确实有效、等待锁后期限越过时拒绝；未过期可只读生成 Precheck；NetworkPolicy head/revision/receipt 未增加。方案/代码复核与相邻回归后精确提交，更新 AOS/Prime，立即进入非特权原子消费施工。当前正式 checker/issuer/Host与首链仍 pending。
