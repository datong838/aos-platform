# AR2-7D Content Generate Agent / Responsibility / Capability 权威

基线 `m1@c45a7eb7`。依据 231-6 D1，在 Handoff、Task、Brief、GrowthPlan 与源 Artifact 输入链已经闭合后，继续闭合 ContentCapabilityRequest 的执行主体和能力目录前置权威。本切片只复验当前 AgentInstance、当前 ResponsibilityPlan 与当前 CapabilityRevision，不启动 Capability、不预留预算、不调用 Provider。

## Owner 与映射

- AgentInstance 以 tenant-scoped `public.aip_agent_instance` 和其绑定的全局 `public.aip_agent_template_revision` 为 Owner；在 Host 事务中对实例行 `FOR SHARE`，要求状态仍为 `active`，按 `AipAgentRegistryStore._instance_snapshot/_hash` 重算当前 version 摘要。包合同使用 `AgentInstanceRevision`，平台 Owner 使用 `AgentInstance`；只在 Host 边界把当前 `instanceId + version + sha256(snapshot)` 映射成包 exact ref，不改公共 DTO 或持久化类型。
- ResponsibilityPlan 以 tenant-scoped head/revision 为 Owner；锁定 head，要求命令 revision 同时等于 current_revision 与 version，并按 create/revise 的原始 JSON 字段口径重算正文摘要，拒绝 DTO 可能归一化的 `true/1` 等弱类型漂移，lifecycle 必须为 `frozen`。复用 `AipProductionContractStore.get_responsibility_plan` 的动态 blockers 算法，要求 readiness=`ready`、coverage=`complete`、blockers/uncovered 均为空；同时要求至少一个 slot 的 assignee 精确指向上述 AgentInstance 当前 version，且该 slot 的 requiredCapabilityIds 包含命令 Capability ID。
- CapabilityRevision 以全局 `public.aip_capability_revision` 为 Owner；按 `AipCapabilityRegistry._from_row` 解析，要求命令引用精确匹配存储摘要、lifecycle=`published`、readiness=`available`、readinessReasons 为空，并且不存在同 capability_id 的更高 published revision。全局目录不伪造 tenant 归属。
- 为使原 ResponsibilityPlan Owner 在 Host/TEMP 环境中仍读取 canonical public 表，只把 `get_responsibility_plan`、assignee resolution 与 readiness blockers 本路径涉及的五处查询表名显式限定为 `public.`；不改变其业务判定。

## 修改与验证范围

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`，在现有 ContentGenerateHostService 输入链末尾增加三类 authority revalidate。
- 修改 `services/aos-api/aos_api/aip_production_contract_store.py`，对上述只读 Owner 路径补充 public schema 限定。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_agent_capability_authority.py`，覆盖正常映射以及 Agent 状态/version/hash、计划 current/frozen/readiness/slot、Capability latest/lifecycle/readiness/hash、tenant 与 TEMP/public 约束。
- 运行本切片专项测试、现有 ContentGenerate/Review 邻接测试、ProductionContract Owner 相关测试、AR2 closure 与 memory validate；核对实现与本文一致，再落 verification 证据并精确提交。

## 边界与下一步

本切片不实现 `execute/verify`，不创建 CapabilityInvocation/Artifact，不读取 Secret，不调用或重试 Provider，不产生费用、审批、发布或业务写入，也不把 ContentGenerate 加入 readiness seal。下一切片继续 ModelRoute、Pricing、Approval、Budget、Capacity 当前权威，随后才进入复用 7A Receipt-first 的无真实 Provider 状态机；230 L0 保持单独挂起。
