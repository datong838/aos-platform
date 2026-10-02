# E17-s3o-i｜AgentInstance Registry 原事务发行身份隔离计划

基线 `m1@af62b3ac`、`AOS-001193`。已复习 231-4/231-9、aip6_001/aip6_002、s3oh Registry 直写 RED 与原 `AipAgentRegistryStore.create_instance/update_instance`。当前权威库只读，Alembic head 保持 `a0v_135`；本波在自动创建/销毁的 test-only PG 仅处理 AgentInstance/Registry Receipt 同事务，不把模板夹具当正式发布。

文件级：新增 `services/aos-api/aos_api/aip_registry_issuer_connection.py`（默认关闭，独立 `aos_aip_registry_issuer` 登录、私有 passfile、精确库/租户/超时、非 owner/BYPASSRLS、无 runtime membership、两个目标表窄 ACL 读回）；新增 `services/aos-api/tests/aip/test_e17_s3oi_registry_issuer_pg.py`（独立真实 PG 角色及同事务原 Store 正负测试）。原 `aip_agent_registry_store.py` 优先不改，用已有 `connect_factory` 注入，不复制 Receipt/hash/CAS 逻辑；代码数据库迁移和 API 正式接线另波。

顺序：

1. RED 已由 s3oh 证明普通 runtime 直插 Registry Receipt 可成功（strict xfail）。进一步在 disposable PG 只撤 Registry Receipt INSERT，调用原 `create_instance` 应因同事务写 Receipt 被拒、AgentInstance 行回滚0；记录当前 Store 未有独立发行身份的失败。
2. 隔离数据库中建独立非 owner/non BYPASSRLS 登录，不授 `aos_runtime` 成员；仅模板 SELECT、AgentInstance SELECT/INSERT/UPDATE、Registry Receipt SELECT/INSERT 和各自租户 RLS。对普通 runtime 撤 Registry Receipt INSERT/UPDATE/DELETE；独立 issuer 与普通 API 登录不得互相 SET ROLE。私有 passfile 不打印。
3. 原 `create_instance` 与精确重复幂等键回读同 Receipt 正向；冲突、跨租户、无凭证/错误身份、Receipt UPDATE/DELETE、普通 runtime 直插负向。只有在隔离角色证明原命令与 Receipt 同事务后收口；Skill/Capability/Tool 原命令留下一波。
4. 专项/相邻回归、py_compile、方案/代码复审、verification、m1 精确提交、上下文/Prime/D-waves 同步。代码头/当前库不漂移，原签名服务只有在预检及备份核对后局部重载。当前正式 issuer/外部 OIDC 和主库 ACL 切换需另波新全备、ACL-faithful 克隆和零执行窗口。
