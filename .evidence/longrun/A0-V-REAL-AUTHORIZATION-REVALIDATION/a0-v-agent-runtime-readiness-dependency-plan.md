# A0-V Agent Runtime 准备依赖审计方案

## 1. 问题与目标

Canonical 电商安装已经批准，七类 Runtime 配置策略已通过正式 Store 建立，但六个电商 AgentInstance 仍为 `provisioning`。当前 37 个 SkillTemplate 仅为 `evaluated`，10 个 CapabilityRevision 虽已 `published`，其 definition readiness 仍被 Provider、EvalPack、W0B contracts 和 AIP-7 route authority 阻塞。

本阶段先建立一个只读、确定性的依赖审计器，冻结实际数据库中的依赖图、首个未满足门和下一可执行切片。审计结果不能把计划、静态定义、Prime/Copilot OAuth、环境变量或人工说明当作运行权威。

## 2. 施工文件

- 新增 `scripts/a0v_agent_runtime_readiness_dependency.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_agent_runtime_readiness_dependency.py`。
- 证据写入 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`。

本切片不修改产品 Router、运行时、数据库 schema 或现有权威对象。

## 3. 固定审计范围

- positive tenant：`org-org/dev-project`。
- isolation canary：`dev-org/dev-project`。
- 数据库只接受隔离恢复库 `aos_meta_head`，容器固定为 `aos-a0v-recovery-pg`，Docker context 固定为 `colima-aos-extension`。
- 精确集合：6 个电商 AgentTemplate/AgentInstance、37 个 `ecommerce.skill.*`、10 个 canonical Capability。
- 配置链：egress、data classification、network、BudgetRevision、quota、BudgetPolicy、RuntimePolicy 和 frozen ResponsibilityPlan。
- 运行链：ProviderInstance、Provider health、ModelRoute、Eval contract/gate、LogicRevision/publication、Skill publication、CapabilityBinding、SkillBinding、AgentInstance activation。

## 4. 依赖顺序与诚实门

1. 安装与七类配置权威必须保持 exact/current；缺失时停止后续写入。
2. Capability definition 的 `eval_pack_unavailable` 只能由正式 Eval Registry 中与当前签名制品同源的 exact EvalPack 消除；`w0b_contracts_unavailable` 只能在 21 号 ADR 的八类公共生产对象关系、RLS/FORCE RLS 与唯一 Store 边界验真后，由新 immutable revision 消除。旧 W-D1～W-D3 脚本仅作历史实现线索，当前库缺少它们依赖的模板 Binding 和 EvidenceBundle，不能直接运行。
3. `provider_unknown` 与 `aip7_route_authority_unavailable` 只能在真实 ProviderInstance、当前健康观察、active ModelRoute、RuntimePolicy 和 exact Eval gate 全部成立后消除；Prime 的 GitHub OAuth 不属于这些权威。
4. 37 个 SkillTemplate 只能通过 `AipSkillPublicationService` 从 exact evaluated revision 发布，必须引用 passed release gate、PublicationEvent、active route/policy 和已发布 LogicRevision。
5. CapabilityBinding 必须经正式 readiness service 形成短时、exact 依赖快照，再激活为 healthy；SkillBinding 必须绑定 published skill 与这些 CapabilityBinding，并独立评估/激活。
6. AgentInstance 只能在 exact published AgentTemplate 与 fresh healthy CapabilityBinding 成立后由 activation service 从 `provisioning` 转为 `active`。
7. 六个实例全部 active 后，才允许正式 materializer 冻结 ResponsibilityPlan；随后重新运行四源 configuration authorization。

## 5. 输出合同

审计器输出：

- 固定 scope、数据库 identity、检查时间和零副作用计数；
- 每一层 `expected/actual/status/blockers`；
- 能力 definition blocker 的去重全集；
- 六个实例与 37 个技能的状态分布；
- canary 对所有 tenant-scoped runtime authority 的计数；
- `firstUnsatisfiedGate` 和 `nextAction`，两者由固定优先级计算，不由模型临场选择。

只有所有层真实满足时才输出 `A0V_AGENT_RUNTIME_READINESS_GREEN`。当前任一门缺失时输出 `A0V_AGENT_RUNTIME_READINESS_BLOCKED`，但脚本执行成功仍返回 0；数据库身份漂移、集合超出、canary 非零或查询失败才返回安全失败。

## 6. 验证与退出

- 纯测试覆盖 gate 优先级、集合精确性、blocked/green 聚合和 canary fail-closed。
- 实际隔离库运行两次，结果除 `observedAt` 外一致，mutation、Provider invocation、external publication 均为 0。
- 证据必须列出下一切片及其真实前置条件，不能以审计完成冒充 Agent runtime ready 或 A0-V GREEN。
