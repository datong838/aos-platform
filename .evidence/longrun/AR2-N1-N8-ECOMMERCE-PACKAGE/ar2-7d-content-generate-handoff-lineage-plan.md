# AR2-7D Content Generate Handoff / Task / Brief 输入权威

基线 `m1@674e3f91`。依据 231-6 D1，`ecommerce_growth_content_generate` 当前只有 adapter spec，尚无 HostService。先闭合能力调用之前的内容任务输入：ContentCapabilityRequest 的严格命令包络、ReviewDecisionReceipt ACCEPT 输出、Handoff、Task、当前 TaskBrief、当前批准 GrowthPlan 与四个源 Artifact 必须是 Review 已交付的同一条 authority 链。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：增加 content generate strict command parser；从 `public.ecommerce_growth_runtime_command_receipt` 回读唯一 ReviewDecisionReceipt，重算正文摘要并要求 ACCEPT、Handoff/Task/Brief/GrowthPlan/四 Artifact 与命令完全一致。
- 同一事务共享锁定当前 Task 与 TaskBrief head，回读 Task、Brief revision/Receipt 的原始 public Owner 字段，沿用 Review Host 的 canonical 请求/内容摘要算法，要求 Brief 仍是 current draft、Task goal 与 Brief spec 仍绑定同一 Handoff、GrowthPlan 和四 Artifact。
- 复用 Review 的 GrowthPlan 当前 Owner 规则；四 Artifact 通过已持久且重新验真的 ReviewDecisionReceipt 回链其当时完成的 Owner 校验，不重复声称第二次读取 Artifact Owner。增加确定性与隔离 PostgreSQL 测试，覆盖正常回链、Review receipt/hash/decision、Handoff、Task、Brief current/version/spec、GrowthPlan、Artifact 引用、tenant/TEMP 与回滚。

## 边界与退出

本切片只建立 ContentGenerateHostService 的严格前半段输入 revalidate，不预留预算、不创建 CapabilityInvocation、不解析 Secret、不调用 Provider、不创建输出 Artifact，也不把类/方法形状加入 readiness seal。后续切片继续 AgentInstance/Responsibility/Capability/ModelRoute/Pricing/Approval/Budget/Capacity 权威和 7A Receipt-first 状态机。专项、邻接、closure、memory validate、diff check 与独立只读复核通过后提交；230 L0 保持挂起。
