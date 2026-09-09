# AR2-7D Content Generate Binding Dependency Owner 验证

- 验证时间：2026-09-09T08:39:10Z
- 基线：`m1@28deea06`
- 方案：`ar2-7d-content-generate-binding-dependency-owner-plan.md`
- 结论：`AR2_7D_CONTENT_GENERATE_BINDING_DEPENDENCY_OWNER_GREEN`

## 已证明

- CapabilityBinding 的 EvalContract exact ref 回读当前 head 与 frozen revision，按 Owner create/revise 的八个原始正文字段复算 canonical hash，并限制 created_at 不晚于统一 cutoff。
- license ResourceRef 原文严格保留，revision 仅接受规范十进制字符串；每项 exact EvidenceBundle id/revision 必须 frozen、license_summary 非空、cutoff 前创建，且其真实存储 hash 对应的撤销事件在 cutoff 前不存在。
- Capability 原始 required data/tool refs 在 DTO 前检查 strict revision 与 canonical 等值；required 全集由 snapshot 覆盖，snapshot 所有 provided refs 只接受现有 Owner 支持的 EvalDatasetRevision/EvidenceBundleRevision，并逐项核 exact hash、created_at 与 Bundle 撤销事件。
- 所有读取复用 ContentGenerate 同一事务和 tenant `public` Owner；revision 共享锁不被描述为可阻止并发追加撤销，结论限定为 cutoff 快照。
- 无 Contract/Evidence/Dataset/Binding 更新、readiness evaluate、AgentRun 推进、Secret 读取、Provider 调用或外部副作用。

## 验证结果

- 聚焦：61 passed；包含隔离迁移 PostgreSQL EvalContract 组合查询。
- 扩展：244 passed，覆盖 ContentGenerate/Review、Binding readiness/API、ProductionContract 与 AgentRun 邻接。
- Python 编译、`git diff --check`：通过。
- AR2 closure：1707/91/57，五类错误数组为空。
- memory validate：`AOS-000571`、`GREEN`、Delivery Receipt 865、Task Receipt 846、Event 2226。
- 独立只读终审：三项 blocker 修复后无剩余 blocker，未发现新增副作用。

## 文件摘要

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：`f5d5ac000109390503586b090f7ba70f154a8b06bfebe584779eacf5f58ed8f6`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`：`9fd4b77f65bff068affc93c7f8b07fa1c4d1d5936c55622df96e1aad26fb3a48`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_agent_capability_authority.py`：`02a456d35a7f2735b9edb5255df6a17bb18f9d88d5ce389c3a83ae706392fb9b`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_binding_dependency_owner.py`：`ce4d11b879507101a1deda69bee8d262862bef0baa5c8b09494a01ef6cd44783`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7d-content-generate-binding-dependency-owner-plan.md`：`ad1ca8d41f400339d9fc0da7633036d4a968a7b197bd7011c0702b3f8c5d1e57`

## 保留边界

本结论不把 snapshot 当作依赖永久有效，也不构成完整执行授权。事务隔离与 cutoff 决定本次快照，并发追加撤销将在后续事务拒绝。7A receipt-first execute/verify、真实 Provider、费用和任何外部效果仍未授权；230 L0 保持挂起。
