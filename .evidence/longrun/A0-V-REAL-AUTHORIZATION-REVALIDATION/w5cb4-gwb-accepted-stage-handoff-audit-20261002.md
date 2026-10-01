# GW-b｜已接受方案至内容 Handoff 来源差距审计

2026-10-02 05:38 CST；基线 AOS-001096 / m1 `840841e7`。只读代码与 231-5/231-9、D-waves BG00GW-b；未写真实库、未触发 Host/Provider。

| 核对点 | 当前证据与结论 |
|---|---|
| 已有合法来源读者 | `aos_api/ecommerce_analyst_stage_handoff_source.py:24-54` 的 `read_approved_stage_handoff_source` 在同事务核当前 accepted StageDecision、原 draft、approved GrowthPlan successor、StageAttempt/EvalReport/Artifact、时限；仅返回来源，不授予 Handoff。`test_analyst_stage_handoff_source_pg.py` 在 disposable PG 验精确/撤销/到期，但决策由 fixture 发布，不是当前业务人工决定。 |
| 现有 bundle producer | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_review_command.py:74-181` 的 `ReviewHandoffRequest` 强制 `review_issue_ref: ExactRef`、`review_issue_status=OPEN`、四种 AIP `ArtifactRevision`，发出的 payload 固定 `reviewIssueRef`；无 `stageDecisionRef`。 |
| 宿主准入 | `aos_api/ecommerce_growth_runtime_adapters.py:2201-2219` 的严格字段集合固定 Issue；`:2583-2683` 读 OPEN `aip_review_issue` 并核 EvalReport，`:2692+` 还要求四个 AIP Artifact 中包含 Issue subject；`:2915+` Handoff hash 绑定 `reviewIssueRef`。直接把 Issue 改 nullable 会破坏原 lineage 与回执语义。 |
| 另一种 Artifact | `aos_api/ecommerce_analyst_stage_decision.py:13-70` 的 accepted stage `artifact_ref` 类型是 `Artifact`，与 Review 的四种 `ArtifactRevision` 不同；不能冒充同一引用。 |

**设计结论**：先明确 StageDecision→Handoff 的第二种严格命令和 Artifact 映射，并同步 bundle producer 与宿主读者/回执；随后用原 Store 人工阶段决策链写 RED 和 PG 联合正反测试。现状不支持正常接受方案无 OPEN Issue 直接创建内容任务，因此普通 Task 自然来源与 Eval 同桶正向仍缺。该缺口局限于 GW-b/普通正向；GT-b4b 正式 Provider 物理容量、当前实例安全迁移门可独立推进。此审计不是实现 GREEN、不是自然首链通过。
