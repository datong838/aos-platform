# AR2-7D Content Generate Skill / Capability Binding 当前权威

基线 `m1@753f0083`。依据 231-6 D1、AIP-6/BIND-1/BIND-3 Owner，在已闭合 Agent、Capability 与 ModelRuntime/Capacity tuple 后，补齐 AgentRun 实际 SkillBinding 及其 CapabilityBinding 的当前执行绑定。全段只读复验现有绑定，不 evaluate、不 activate、不读取 Secret、不调用 Provider。

## Owner 与判定

- AgentRun 必须提供非空 `skill_binding_id` 与 exact `skill_ref`。从 tenant `public.aip_skill_binding` 共享锁定该行，要求绑定属于命令 AgentInstance、状态 ACTIVE、严格整数 version、Skill exact ref 与 AgentRun 一致，且自身 readiness 为 AVAILABLE、无 reasons、`last_evaluated_at <= cutoff < readiness_expires_at`。
- SkillBinding 的 route、runtime policy、route eval gate 与 budget policy snapshot 必须分别等于本次已验证的 Route、Policy、Route EvalGate 与 Policy BudgetPolicy；所有原始 JSON exact ref 在 DTO 解析前拒绝 `true/1` 弱类型，再依据 `AipSkillBindingReadinessService.snapshot_hash` 和实际绑定的 CapabilityBinding 行重算 dependency snapshot。
- SkillBinding 列出的 CapabilityBinding ID 必须唯一非空，且至少一个 tenant binding exact 覆盖命令当前最新 CapabilityRevision。所选 CapabilityBinding 必须 ACTIVE、HEALTHY、严格整数 version、`observed_at <= cutoff`、operational readiness AVAILABLE、无 reasons，并满足 `last_evaluated_at <= cutoff < readiness_expires_at`；不接受 degraded/allowDegraded 放宽。
- CapabilityBinding 的 dependency snapshot 按 `AipBindingReadinessService.snapshot_hash` 由命令当前 CapabilityRevision 与原始 dependencies 重算，所有原始 VersionedAssetRef 同样先做严格整数 revision 检查。Provider、ModelRoute、RuntimePolicy、Route EvalGate 与 BudgetPolicy 必须逐项等于同次已验证 resolution；EvalContract、license/data/tool refs 保持在已求值 snapshot 中，本切片不把 snapshot 冒充这些 Owner 的永久有效性。
- SkillTemplate revision 必须是 tenant 已发布 exact revision，原始 content hash、publication tenant、Route/Policy/EvalGate 与命令链一致；其 required capabilities 必须由 SkillBinding 的 CapabilityBinding 集合覆盖，且当前命令 Capability 是所需项。

## 修改与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：让既有 Agent/Capability 与 Resolution/Capacity 复验返回后续所需 typed authority；扩展 AgentRun 查询，并新增 Skill/Capability Binding 只读复验。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_binding_authority.py`；调整既有 ContentGenerate 单元替身。覆盖 exact 正例、run/skill/binding关联、状态与时间窗、snapshot hash、Capability exact revision、Route/Policy/Gate/Budget dependencies、tenant/public、重复ID与 `true/1` 反例。
- 在 pytest 自动迁移并销毁的隔离 PostgreSQL 上执行真实组合查询；回归 ContentGenerate/Review、AIP binding/readiness/AgentRun 邻接、AR2 closure 与 memory validate；独立只读终审通过后落 verification 并精确提交、同步 docs。

## 边界与下一步

本段不创建或更新 SkillBinding/CapabilityBinding，不 evaluate/activate，不推进 AgentRun，不创建 CapabilityInvocation/BudgetReservation/Artifact，不解析 Secret，不调用 Provider，不产生费用或外部副作用，不加入 readiness seal。EvalContract、license/data/tool 各自 Owner 的 cutoff 重验和 7A Receipt-first execute/verify 仍属后续；230 L0 保持挂起。
