# GW-b-2c2c1b3c2c｜当前配置/身份精确审计

基线 `AOS-001120`、`aos-platform/m1 27d47fd5`，上位231/231-1/231-2/231-4与同名 plan 已复习。此波只读，不制造配置/账号/批准，不修改服务或业务代码。

| 项 | 当前真实回读 |
|---|---|
| 权威库 | `aos_current_preview_20260927@a0v_135`，原卷 `aos-a0v-recovery-pg-data`；`read_candidates(conn,TenantScope('org-org','dev-project'))` 在只读事务返回八类候选 `responsibility_plans/runtime_policies/data_policies/egress_policies/network_policies/quota_policies/budget_policies/budgets` 全0。 |
| 运行与安装 | SQL 只读计数：正租户 Host assignment0、启用Host identity0、runtime binding0、Growth1.13 published0；当前旧正式安装 approved1、active revision NULL。 |
| 正式 API | `a0v_current_preview_http.py --serve-limited --api-identity-file /nonexistent/aos-api.json` 退出2，`SAFE_BLOCKED/EXTERNAL_OIDC_CONFIG_REQUIRED`，未连接/启动第二API；当前 LaunchAgent 无 `AOS_OIDC_*`/`AOS_AUTH_*` 环境键。已找到的 `api-service-identity.json` 仅在 `aos-recovery/.aos-testonly-bg00cf-*`，不能当当前正式凭据。 |
| Runtime Host | `a0v_current_runtime_host_preflight.py --signed-receipt <当前>` 退出2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`；18181仍无监听。 |

`runtime_configuration_candidates.py` 明示租户候选计数不绑定某安装，且有专项测试；Host预检先检三身份/assignment再读候选。此次没有发现应在候选 reader 上做的最小修复，故不制造冗余 helper 或重复测试来刷进度。当前实例正式启用受外部 IdP/独立身份/Owner/八配置权威约束，仅阻断该实例。下一安全代码波转回已登记 GW-b 原 BI→Stage→Task/Brief v3 的 exact 来源与写链，不依赖当前外部身份。无商城源读取、dev-org写、Run重放、手工Run、Provider/Host启动或push。
