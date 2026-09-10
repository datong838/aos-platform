# A0-V 当前 Runtime 配置权威修复方案

## 1. 问题与目标

Canonical 电商安装已批准，但 runtime mutation 前置检查确认 `org-org/dev-project` 的八类配置权威候选全部为 0。目标是只用现有生产 AIP Store/合同建立可重放、可回读、fail-closed 的 development 配置链，使 `CurrentFourSourceConfigurationAuthorization` 能独立重验，不把测试 fixture、直接 SQL 或环境变量当权威。

本阶段不启动 runtime 容器，不调用 Provider，不创建模型路由，不访问真实业务数据，不执行外部网络或业务写入。

## 2. 施工文件

- 新增 `scripts/a0v_current_runtime_configuration_authority.py`
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_current_runtime_configuration_authority.py`
- 修改 `scripts/a0v_canonical_ecommerce_first_install.py` 仅在配置权威 GREEN 后消费该脚本封存的 exact 配置 receipt；不得从候选计数自行选择任意对象。
- 证据写入 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`

## 3. 权威依赖顺序

1. `AipRuntimeGuardPolicyStore` 发布 active/effective egress 与 data-classification policy。
2. `AipNetworkPolicyStore` 发布只允许固定本地开发目标、禁止 public fallback 的 network policy，并 exact 引用 egress。
3. `AipBudgetAuthorityStore` 发布 CNY、hard-stop、unknown=block 的 development BudgetRevision。
4. `AipModelGovernancePolicyStore` 发布 quota 与 budget policy；禁止自动扩容和公共 Provider fallback，budget policy exact 引用 BudgetRevision。
5. `AipModelRuntimeStore.publish_policy` 发布 kill-switch=false 的 RuntimePolicy；正式 Store 必须重验 network、egress、data、quota、budget-policy 全部 exact/current/effective。
6. `BusinessInvestigationAuthorityMaterializer` 通过 `AipProductionContractStore` 建立正式调查 StageTemplate 与 ResponsibilityPlan。只有六个指定 AgentInstance 已 active 且计划 readiness=ready 时才 freeze；否则保留 draft 并输出原始 blocker。
7. 生成只包含四个 `ConfigurationSourceRef` 和 `ConfigurationDocument` 的仓库外 receipt；内容 hash 来自权威对象，不包含 secret、token 或连接参数。
8. 采用 `aos_runtime` + tenant scope 调用 `build_current_configuration_authorization` 对整份 ConfigurationDocument 做一次只读验真。只有验真成功才标记 `A0V_CURRENT_RUNTIME_CONFIGURATION_AUTHORITY_GREEN`。

## 4. 固定安全参数

- tenant：`org-org/dev-project`；canary `dev-org/dev-project` 必须保持所有对应 head 为 0。
- environment：`development`。
- policy effective window：固定 UTC 起止时间，不随重放漂移；到期后必须新建 revision，不能静默延长旧 revision。
- data：只允许 `public_catalog`；明确禁止 PII、订单明细、客户对话、凭据、经营敏感、跨租户和 unknown。
- egress/network：只允许方案中固定的本地开发 endpoint；public fallback=false、unknown destination=block、TLS required。
- quota：低并发、低请求量、overflow=queue、auto-scale=false、public provider fallback=false。
- budget：CNY hard-stop；unknown usage/price=block；不允许零价格；金额只是上限权威，不授予 Provider 调用。
- RuntimePolicy：有限 deadline/attempt，fallback reason 为空，kill switch=false。该状态仅允许 runtime 配置校验；Provider/模型/路由仍须通过 A0-V 独立健康和批准门。

## 5. 幂等与失败关闭

- 每个 Store 使用固定 idempotency key 和固定 revision=1；首次创建后重放必须返回相同 resource id/revision/content hash。
- 既有同 id 对象、Receipt 或 head 与固定 payload 不一致时停止，不更新或覆盖。
- 任一依赖 Store 拒绝，保留已成功的不可变前置资产并从其 Receipt 续跑。
- ResponsibilityPlan 未 frozen 时不生成可消费的 role ref；首装仍保持 approved、runtime operation/binding 为 0。
- 配置 receipt 必须在全部四源 readback 通过后原子写到仓库外 state 目录；失败结果可进证据，但不得伪标 GREEN。

## 6. 验证与退出

- 单元测试覆盖错误 tenant、可变时间/幂等漂移、unsafe policy、canary、未 frozen plan 和四源 readback。
- 运行相关 guard/network/governance/budget/model-runtime/production-contract 专项。
- 实际首次与重放结果必须对象/hashes 相同，第二次 mutation count 为 0。
- 只有 frozen ResponsibilityPlan、active RuntimePolicy、exact data/Budget ref 和整份 `CurrentFourSourceConfigurationAuthorization` 通过，才退出为 `A0V_CURRENT_RUNTIME_CONFIGURATION_AUTHORITY_GREEN`。

若正式调查计划因 AgentInstance/Capability/Skill/模型权威未就绪而保持 draft，本切片退出为 `A0V_CURRENT_RUNTIME_CONFIGURATION_AUTHORITY_BLOCKED`，并把这些真实 blocker 交给 A0-V 下一修复项；不得创建简化 legacy 计划绕过调查链。
