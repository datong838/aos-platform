# AR2-7D Content Generate Skill / Capability Binding 验证

- 验证时间：2026-09-09T08:16:31Z
- 基线：`m1@753f0083`
- 方案：`ar2-7d-content-generate-binding-authority-plan.md`
- 结论：`AR2_7D_CONTENT_GENERATE_BINDING_AUTHORITY_GREEN`

## 已证明

- AgentRun 的 exact Skill ref 与 SkillBinding ID 回链到 tenant 当前 ACTIVE、AVAILABLE、未过期 SkillBinding；Skill 发布 tenant、Route、Policy、EvalGate、BudgetPolicy 与本次已验证 resolution 完全一致。
- Skill required capabilities 由绑定集合完整覆盖；集合内每个 CapabilityBinding 均逐项 ACTIVE、HEALTHY、AVAILABLE、在 cutoff 已观测且 readiness 未过期，目标绑定 exact 命中命令当前最新 CapabilityRevision。
- SkillBinding 与目标 CapabilityBinding 的 dependency snapshot 分别用既有 Owner 算法重算；所有原始 VersionedAssetRef 在 DTO 前执行严格整数 revision 与 canonical JSON 等值检查，关闭 `true/1`、空白 strip 及保留旧 snapshot 绕过。
- 查询仅取绑定判断字段，不读取 `secret_ref`；全程只有 tenant `public` 只读查询与共享锁。

## 验证结果

- 专项：21 passed；包含隔离迁移 PostgreSQL Skill Owner 组合查询。
- 扩展：195 passed，覆盖全部 ContentGenerate/Review、Capability/Skill Binding readiness/API、Agent activation 与 AgentRun 邻接。
- Python 编译与 `git diff --check`：通过。
- AR2 closure：1707/91/57，五类错误数组为空。
- memory validate：`AOS-000571`、`GREEN`、Delivery Receipt 865、Task Receipt 846、Event 2226。
- 独立只读终审三轮：最终无剩余 blocker；确认原始 ref、全集覆盖、逐项状态/时间均闭合且无副作用。

## 文件摘要

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：`76602af4b83937dd3e87f723d4f64fbda93148bc84e2ec26131983e576af4e08`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`：`d0c6f77800071e9701faeef81756366a1e38955101d191effa3483c1bfa80bc5`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_binding_authority.py`：`f89214cecae8e87d9f9ad69cd0abdbf49d639dfa805e19f5a39161c08140629d`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7d-content-generate-binding-authority-plan.md`：`22db155479597b5e6e856148b15f16647447cc12fd5b5280a05de87913f1853e`

## 保留边界

本切片不把 freshness snapshot 冒充 EvalContract、license/data/tool Owner 的永久有效性，也不构成完整执行授权。不创建或更新 Binding，不 evaluate/activate，不推进 AgentRun，不创建 Invocation/Reservation/Artifact，不解析 Secret、不调用 Provider、不产生费用或外部副作用。各依赖 Owner 的 cutoff 重验和 7A receipt-first execute/verify 继续后续；230 L0 保持挂起。
