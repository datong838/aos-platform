# E17-s3o-i｜AgentInstance 原 Store 独立 Registry issuer 隔离 verification

基线 `m1@af62b3ac`、`AOS-001193`。复习 231-4/231-9、aip6_001/aip6_002 和 s3oh RED；文件级计划见同前缀 plan。所有角色/GRANT/REVOKE/RLS 只在 test-only PG 的随机 disposable DB，代码及当前库 Alembic head 仍 `a0v_135`，当前原卷无写。

| 步骤 | 新鲜结果 |
|---|---|
| 原路径 RED | 仅在随机测试库撤普通 `aos_runtime` 的 Registry Receipt INSERT/UPDATE/DELETE，原 `AipAgentRegistryStore.create_instance` 无独立身份时因 Receipt INSERT 报 `InsufficientPrivilege`，外层 `AipAgentRegistryPersistenceError`，exit1；例外支路只读查询 AgentInstance 行为0，证明同事务未留半成品。|
| 独立连接 | 默认关闭的 `aip_registry_issuer_connection.py` 仅供原 Store `connect_factory` 注入；私有0600 passfile/0700父目录、精确回环库、固定 SQL 超时/search_path、真实非 owner/non BYPASSRLS `session_user=current_user=aos_aip_registry_issuer`，拒 `aos_runtime` 成员；读回 Registry Receipt RLS/SELECT/INSERT且无 UPDATE/DELETE、普通 runtime 无 INSERT，AgentInstance RLS/SELECT/INSERT/UPDATE且无 DELETE、模板 SELECT、跨域 Binding/Assignee 无写。|
| 隔离 ACL | test-only 独立登录不继承 runtime；模板 SELECT、AgentInstance SELECT/INSERT/UPDATE、Registry Receipt SELECT/INSERT；两个租户表独立 org/project RLS。正式 migration 未写入代码或当前库。|
| 原命令正向 | 原 `create_instance` 同事务生成 AgentInstance 与 applied Registry Receipt；相同 idempotency key 返回同一 Receipt；`update_instance` provisioning→active 同事务生成第二 Receipt；普通 runtime SELECT 回读两种 operation。模板由隔离夹具构造，**不等于正式签名发布来源**。|
| 负例 | 普通 runtime 直接 Registry INSERT 被拒，`dev-org` 零副作用只读 canary 看不到 org-org Instance；issuer 对 Skill/Capability/Tool/Assignee 无 INSERT；非私有 passfile拒绝、再次放宽普通 runtime Receipt INSERT 时连接预检拒绝。测试结束 issuer 全局角色清零。|
| 测试 | `pytest -q tests/aip/test_e17_s3oi_registry_issuer_pg.py tests/aip/test_aip_agent_registry_store.py --tb=short` → exit0，8 passed/7 warnings；`py_compile`、目标 diff check exit0。|

方案/代码一致性：原 `AipAgentRegistryStore` 的幂等、hash、状态转移、CAS 与 Receipt 同事务算法未改，只注入独立连接；新模块不自动加入 API/Host。Skill/Capability/Tool 同事务 Registry 写路尚未以此身份验证；当前原库 `aos_runtime` 的 Registry 直写依旧为 strict xfail，正式 OIDC/凭证、当前迁移/切换和六绑定/八配置/Host/自然首链仍未完成。下一波先补该 issuer 的 Skill/Capability 原 Store 兼容与权限边界，再另波做可恢复的当前 ACL 迁移。
