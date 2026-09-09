# AR2-7D Content Generate Binding Dependency Owner 当前权威

基线 `m1@28deea06`。上一切片证明 Skill/Capability Binding snapshot 当前、完整且与 ModelRuntime resolution exact 一致；本切片继续按 BIND-1 authority 的既有口径，只读复验 snapshot 中尚未逐项回读的 EvalContract、license evidence、data 与 tool dependency Owner。不得把未过期 snapshot 单独当成依赖持续有效的证明。

## Owner 与判定

- CapabilityBinding 必须带 exact EvalContractRevision；从 tenant `public.aip_eval_contract_revision` 回读八个原始正文列并按 Owner create/revise 口径复算 hash，要求 FROZEN，并锁定对应 current head，拒绝旧版、撤回、正文、摘要和 `true/1` 漂移。
- 每个 licenseEvidenceRef 必须是严格十进制 revision 字符串的 EvidenceBundleRevision，authority 保持原文，且 tenant `public.aip_evidence_bundle_revision` exact id/revision 存在、FROZEN、license_summary 非空；该 ResourceRef 合同不携带 contentHash，因此不虚构摘要比较。列表不得为空、重复或经 DTO 归一化改变。
- Capability 当前原始 `required_data_refs`、`required_tool_refs` 在 DTO 前拒绝弱类型与规范化漂移，并必须被 Binding dependency snapshot 全集覆盖。沿现有 `PostgresBindingDependencyAuthority.exact_assets_available` 支持范围，只接受 EvalDatasetRevision 或 EvidenceBundleRevision；逐项回读 tenant public Owner 的 exact id/revision/hash。EvidenceBundle 同时要求 FROZEN且在 cutoff 前没有 exact revoke event；未知类型 fail closed。
- 所有查询复用 ContentGenerate 同一事务与数据库 cutoff；依赖记录 `created_at` 不得晚于 cutoff，EvidenceBundle revoke event 按 `occurred_at <= cutoff` 判定。本段使用事务快照与只读共享锁，不声称 revision 行锁能阻止并发追加撤销事件，不调用 readiness service 的新连接，不写回 snapshot。

## 修改与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：让 Binding authority 返回目标 dependencies，并新增 dependency Owner revalidation。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_binding_dependency_owner.py`，调整既有替身；覆盖正例、EvalContract current/lifecycle/hash、license 空/重复/authority/revision/hash/lifecycle/license summary、required data/tool 全集、未知类型、Owner missing/future 与原始 JSON 弱类型。
- 通过隔离迁移 PostgreSQL 验证组合查询，回归 ContentGenerate/Review、BIND/ProductionContract/Eval 邻接、AR2 closure、memory validate；独立只读终审通过后落 verification、精确提交并同步 docs。

## 边界与下一步

本段不创建或更新 Contract/Evidence/Dataset/Binding，不 evaluate/activate，不创建 Invocation/Reservation/Artifact，不推进 AgentRun，不解析 Secret、不调用 Provider、不产生费用或外部副作用。完成后才评估 ContentGenerate 7A receipt-first execute/verify 的最小无真实 Provider 状态机；230 L0 保持挂起。
