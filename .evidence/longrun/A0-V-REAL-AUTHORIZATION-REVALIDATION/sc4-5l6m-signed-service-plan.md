# SC4-5l6m 独立连接签名分派服务集成

Rules：m1 单写、先方案、隔离数据库、最小测试范围；不 push、不迁移主库，230 L0 挂起。

基线 724c5356。ProductEvent 回归 300 passed、21 skipped；跳过不计验收。RuntimeReleaseRevalidator 内部已持有 Registry advisory lock，不另加重复锁。

新增 services/aos-api/tests/extension_runtime/test_event_control_dispatch_service_pg.py。测试专属临时数据库复用标准 conftest bootstrap/销毁，允许真正提交和独立连接；使用测试密钥签名的 growth 声明与本地 allowlist 合同文件，通过真实 Registry、Composition 与 Installation Store 保存。准备 active 安装及九项分派的 fixture 不代表 OCI 安装验收。Service 必须使用真实 PostgresInstallationStore、ReleasePolicy、CurrentRuntimeReleaseArtifacts 和非超级用户 runtime/maintainer 会话；禁止 monkeypatch 资格/审批/SQL/回执读取。

审批由真实 AipActionStore.decide 产生，独立 Service.transition 消费后新连接核对唯一回执与分派；重复调用回放。错误签名文件、审批漂移或过期不得留下分派变化。完整服务通过后再审视资格到提交之间的时效与回滚边界。

此项只关闭 Service 同事务组合，不自动放开主库 Registry、安装或真实业务验收。
