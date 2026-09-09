# AR2-7D Content Generate Resolution / Capacity 当前权威

基线 `m1@4723dc97`。依据 231-6 D1、AIP-7 ModelRuntime resolver 与 Capacity Owner，在 Route/Price/Budget/Approval 已闭合后，继续证明命令中的 CapacityReservation 确实属于同一当前 AgentRun 与同一 route/model/provider/price resolution。本段只读复验既有 reservation，不创建、消费或释放容量，不读取 Secret，不调用 Provider。

## Owner 与判定

- 复用上一段同一事务、同一数据库 cutoff 和已验证的当前 ModelRoute。首条内部内容链明确只接受含 `content_campaign` 的单候选 FAILOVER Route，固定解析唯一候选，不执行 fallback，也不把 WEIGHTED/延迟策略错误实现成数组首项：RegisteredModel、ProviderInstance、RuntimePolicy 原始 revision payload 均按 ModelRuntime 发布口径复算摘要，要求 exact ref、ACTIVE、模态与 Capability 覆盖一致；Model 必须绑定命令 Price 与 Provider，Route 必须包含该 exact Model，且命令输入输出 token 总量不得超过 Model context window。
- Route 与 Model 的 EvalGateDecision 从 `public.aip_release_gate_decision` exact 回读，要求 PASSED、未失效、在 cutoff 有效并精确绑定各自 evaluation candidate；RuntimePolicy 必须 ACTIVE 且 kill switch 关闭；Provider 最新 health observation 必须 exact、healthy，并满足 `observed_at <= cutoff < expires_at`。全程不解析 Provider `secretRef`。
- CapacityReservation 以 `public.aip_model_capacity_reservation` 可变状态行和其不可变 identity 为 Owner；命令 exact ref 固定 revision=1、contentHash=`sha256:<request_hash>`。要求 `created_at <= cutoff < expires_at`、状态 `reserved`、requestUnits=1，且 immutable request_hash 按既有 `AipModelCapacityReservationGate._request_hash` 由 AgentRun ID、exact route/model/provider、当前 CapacityPool revision 与 token unit 重算。
- CapacityPool 必须是当前 head、ACTIVE，原始字段按 `materialize_capacity_pool` 口径复算 content hash，JSON exact refs 与拆列严格一致；reservation tokenUnits 等于 pool tokenUnitPerReservation，命令 maxInputTokens+maxOutputTokens 不得超过该额度。
- Reservation 反查的 AgentRun 必须当前 RUNNING，Task、AgentInstance ID/version、ModelRoute 与 RuntimePolicy 分别命中本命令已验证权威。只证明现存运行与容量关系，不创建或推进 AgentRun。

## 修改与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：让 route/budget 方法返回同 cutoff 的 route，并增加 resolution/capacity/AgentRun 只读复验。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_resolution_capacity_authority.py`：覆盖 exact 正例、reservation hash/status/创建与过期时间、pool current/hash/ref/token、AgentRun task/agent/route/policy、Model/Provider/Price、Eval、health 观察时间区间与 `true/1` 弱类型反例；Route/Budget 测试覆盖单候选 FAILOVER 限制。
- 回归 ContentGenerate/Review、AIP-7 ModelRuntime/Capacity/AgentRun 邻接；在 pytest 自动创建、迁移并销毁的隔离 PostgreSQL 数据库上直接执行组合 Capacity Owner 查询，证明实际表列与锁语法兼容，不改当前共享测试库；随后执行 AR2 closure、memory validate，独立只读终审通过后精确提交并同步 docs。

## 边界与下一步

本段不创建/更新/消费/释放 CapacityReservation，不创建 CapabilityInvocation/BudgetReservation/Artifact，不改变 AgentRun，不解析 Secret，不调用 Provider，不产生费用或外部副作用，不加入 readiness seal。AgentRun 的 SkillBinding/CapabilityBinding 对最新 CapabilityRevision 与 resolution dependencies 的精确闭合，以及 7A Receipt-first execute/verify 仍属后续切片；230 L0 保持挂起。
