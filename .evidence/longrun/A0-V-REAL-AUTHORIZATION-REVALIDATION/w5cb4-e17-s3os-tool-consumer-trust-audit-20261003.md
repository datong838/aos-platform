# W5CB4 E17-s3o-s｜ToolBinding 消费侧发行信任门审计

日期 2026-10-03。先读231/231-9、128、s3o-q/r、`aip13_001`、`aip6_002`、原 Store/Resolver/issuer 连接与当前卷 ACL；只读，不改当前库/进程/角色。当前 Host/worker/Provider关闭、Goal active。

## 事实

1. 原 ToolBinding upsert 无同事务发行 Receipt；s3o-r disposable PG `assert 0 == 1` 是首次 RED，已保留 strict xfail。原 `resolve` 只按同租户 row/version/status、实例和 CapabilityBinding 状态判断；它的 AssigneeResolutionReceipt 证明解析，不证明绑定签发。
2. 当前权威库在 `conn.read_only=True` 下查 `has_table_privilege`：`aos_runtime` 对 `aip_tool_binding` INSERT/UPDATE 为 true，对 `aip_agent_registry_receipt` INSERT/UPDATE 也为 true。Receipt 的 append-only trigger 防 UPDATE/DELETE，但不阻止当前普通 runtime 自行 INSERT 一个形状合规的新发行 Receipt。故现在若给 Resolver 加“存在 `tool_binding.upsert` Receipt”检查，仍可被当前广权写者同时伪造绑定与回执；不能把它当正式信任门。
3. `aip_agent_registry_receipt` 有 operation/idempotency_key/request_hash/resource_ref/result_ref/status/created_by/created_at 与租户主键，形式上可复用，但该表不绑定专用 Tool issuer。已有 Agent/Skill/Capability 专用发行连接明确拒 ToolBinding cross-domain write；不能借它们的身份。

## 最小可审实现顺序

1. 在隔离 PG135 定义 Tool 专用非 owner/no runtime/no BYPASSRLS issuer，只授原 ToolBinding `SELECT/INSERT/UPDATE` 与 Registry Receipt `SELECT/INSERT`、必要源表 SELECT，所有租户表 FORCE RLS；原普通 runtime 对这两表写要同时收窄。精确建同事务 Receipt、同键同 payload 幂等、同键异 payload 冲突、版本 CAS、撤销/失效、租户负例；不可只加读侧存在检查。
2. 发行请求要有可验证的 Tool、AgentInstance、CapabilityBinding、Policy/安装/批准来源及 actor/idempotency。当前请求缺这些；签名包/Owner 与受限 API 身份还不存在。因此先冻结来源合同与谁有权签发，再修改公共请求/迁移。孤立消费侧 gate 在当前 ACL 下没有可信正例。
3. 当前真实卷切换需另立波：独立新全备及可恢复、ACL-faithful 克隆全链、零执行窗口，正式 OIDC/签名来源和原命令回归。此审计不批准迁移、Host 或自然首链。当前实例局部身份缺口不停止独立代码波。

结论：本波记录信任门前置，不添加可被宽权限伪造的表面校验。下一独立安全候选从 D-wave 的八配置合法生产者/原消费禁入进入；正式 Tool 发行在上述条件齐后实施。
