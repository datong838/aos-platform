# W5cao｜BG-04 已批准武器包方法→内部 Task/Brief 严格接线核验

## 方案、RED/GREEN 与文件范围

上位：231 A1-03/04/05、231-9 BG-03/04、栖月汇双侧增长产品方案。先行方案及第 3 步补充：`w5cao-bg04-authoritative-brief-handoff-plan-20260926.md`；上段提交 `bf90b85a` 已将有来源方法置于当前 GrowthPlan exact hash 并补 Plan Owner 发布 hash 门。本段只改 `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py`、`services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 和对应专项测试，不增 Host 命令字段、第二 Task Owner、Provider 或前端入口。

RED：批准方法的新 `channels/timeWindow` 被旧合同拒绝；Review 对有批准方法却不符的 Task 文本/缺 Decision 来源不拒绝；旧内容生成 Brief 门对 v2 全文拒绝；旧 Review AnalysisRuntimeReceipt 门不核 v2 cutoff。GREEN：

1. `SalesWeaponMethod` 中的渠道/时间窗也进入已批准 Plan hash；Host 从方法确定性构造**全部**内容 Task 业务字段，与包内 W5cak 映射做同值测试。技术商品来源键不进入对人文案。
2. 原 Review Host 在同一 `HostTransaction` 内复用 `require_growth_plan_sources` 和 `require_current_revision`，要求当前 Decision→Insight、EvidenceBundle/原 Evidence、marking 与新鲜度，方法来源是 Decision exact 子集，方法/Insight/Review/原 AnalysisRuntimeReceipt cutoff 同版。DB 时钟必须落在 Review 有界有效期内；不满足时在 Task 创建前拒绝。
3. 原 AIP Task/TaskBrief Owner 创建路径不变；含方法的 Plan 生成 `content-campaign-brief/v2`，完整方法、DecisionRef、cutoff 留在 TaskBrief spec，由原 Owner hash/Receipt/同事务读回；无方法的旧 Plan 仍生成原 v1 spec。
4. 下游原 ContentGenerate Host 先复核当前 approved Plan，再按 Plan 有无方法选择唯一 v1/v2 spec 字段集合；v2 的 schema、方法、Decision、cutoff、Task 标题/目标/渠道/客群/时间/约束必须与批准 Plan 一致；没有 Plan 方法不得接受 v2 Brief。没有放宽为任意 JSON。

## 新鲜验证与结论边界

包含 Plan 合同/Owner/来源、武器包映射、Review 原链/Host/TaskBrief、内容生成 v1/v2/能力邻接、内容评审的本次累计：**276 passed、1 skipped、7 既有 warnings**。隔离 PG 证明 v1/v2 TaskBrief 经原 Owner 持久化/读回和外层 rollback；v2 无当前 Decision 时拒绝、错误 Task 文本拒绝、篡改后即使重新计算 Brief hash 仍不能通过下游 Plan 对账。`compileall` 与 `git diff --check` 通过。没有新增页面，浏览器 N/A。

这只闭合 **BG-04 的批准方法到内部 Task/Brief 技术接线**，没有当前真实商品/Decision/Evidence 全链成功样本、自然 Case/Run→D01/D02/D03、实际 Provider 调用、可读产物、人工评审续跑或 Wiki 候选。现有 `ContentGenerateHostService.execute` 仍是预算占用后 `release_no_effect`，绝不算真实内容生产。方法的来源键不是商品事实证明，SourceReadiness/商品适用性与主张语义仍需在真实链校验。下一波 W5cap 应先钉住 `factSourceRefs` 的当前权威及原 Provider/Artifact Owner，再以有界真实文字产物替换 no-effect；若预算/审批/原模型权威缺失，仅阻止该实例，不读商城源、不手动补 Run。

旧 12 Run 不重播；未知结果不重发；230 L0 挂起，dev-org 仅零 canary，m1 单写不 push。W5cao 不关闭 A1，也不把 276 个测试写成首链通过。
