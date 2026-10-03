# E17-s3o-w-ao-b19｜当前 DB CONNECT 与共享 Receipt operation 负门

## 原库只读权威

- 原卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135` 的 `BEGIN READ ONLY`：`aos_runtime` 对 `aip_capability_binding` SELECT/INSERT/UPDATE 为 true/true/true，对共享 `aip_agent_registry_receipt` INSERT 为 true；Receipt 当前6行均 `agent_instance.create`。`pg_database.datacl={=T/aos_app,aos_app=CTc/aos_app}`，现有非 owner runtime 成员登录 `aos_a0v_runtime_20260912` 和 `aos_ecommerce_registration_control` 对当前库 CONNECT 均 false；唯一可连接的已列登录为超权 `aos_app`。SQL 各 exit0。**表 ACL 宽不等于当前非 owner 登录已经能连接。**
- 原 `AipCapabilityBindingService` 使用 `capability_binding.create/update/evaluate`，先写/更新 Binding 后在同一事务写 Receipt；Receipt `result_ref` 资源类型/ID存在，但 `revision=None`。原 `RegistryIssuerConnectionFactory(capability_lifecycle)` 要求 runtime 对共享 Receipt INSERT=false，此事实与原库 true 冲突；只放松 Python 检查会打开伪造面。

## 忠实 ACL 克隆 RED 与副作用对账

| 门 | 命令/输出 |
| --- | --- |
| 克隆入口 | b17 无网络克隆 `aos_e17_s3owaob17_acl_20261004` 以原 `aos_a0v_runtime_20260912` 独立登录 `psql` → `FATAL: permission denied for database`，exit2。原库相同角色 `has_database_privilege(...,'CONNECT')=false`，是忠实负门，不能说当前直接非 owner runtime 已伪造 Receipt。 |
| 表级 operation RED | 仅在该克隆由可连 owner `aos_app` 开事务，`SET ROLE aos_runtime` 且 scope=`org-org/dev-project`；输出 `session_user=aos_app/current_user=aos_runtime`。同一事务 INSERT 无对应 Binding 的 `capability_binding.create` Receipt 与正常 `agent_instance.create` Receipt `INSERT 0 2`，两类各可回读1；随后 `ROLLBACK`，命令exit0。后读两 Receipt count0、CapabilityBinding0、Installation1，exit0。证明当前 RLS/ACL/约束**没有** operation/同事务绑定门，同时普通 operation 必须保留。 |

## 方案与风险复审

- 当前正式 Reader/Capability issuer role0、独立私有凭据和外部 OIDC缺；非 owner DB CONNECT 也未授。正确顺序是可核来源和私有登录 → 仅精确身份 CONNECT/表 ACL → operation/session/同事务绑定防伪 → API 切换与零执行窗口复演；不能先全局撤共享 Receipt INSERT，也不能让 owner 会话的 RED 冒充可达的非 owner 攻击链。
- 公共持久协议候选须定义 Capability create/update/evaluate 各自 exact Binding版本、租户、Receipt重放/CAS和真实 session_user，并保留其他合法 Agent/Skill/Run operation。现有 Receipt `revision=None`，不宜把 b12 Tool 的 `xmin` test-only 探针无审查搬到生产。本波未写生产代码、迁移、当前 DB、API/Web/UI；浏览器和前端累计测试不适用于只读/回滚负审计。Host/worker/Provider关，八配置/六 Binding/自然首链 pending。
- 下一波先按已有身份部署样板制定 Reader/issuer 当前 DB CONNECT 与凭据来源的可执行门，同时为 operation scoped Receipt 单独做正式协议/测试，不能以全局 owner 或 test-only trust 作正式身份。`org-org/dev-project` 唯一正向，`dev-org` 零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
