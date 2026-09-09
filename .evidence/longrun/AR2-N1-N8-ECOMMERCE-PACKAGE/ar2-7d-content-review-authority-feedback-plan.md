# AR2-7D Content Review 权威与反馈同事务方案

基线 `m1@a6c426c2`。当前固定九 operation 中 `ContentReviewAdapter` 只有登记规格，尚无 `ContentReviewHostService`；N7 包已冻结严格 `content.review` 命令、`ContentReviewReceipt` 与 ACCEPT/RETURN 形状，AR2-7C 已提供 transaction-bound feedback enqueue/recovery port。按 231-6 第 116、133、141、146 条，本切片补齐 Artifact/Task/Brief/Issue/ReviewerAuthority 的真实 Owner 回读，并在同一 HostTransaction 内原子持久化审阅收据与 7C feedback command/outbox。

## 权威读取与严格命令

- 命令只接受 N7 固定字段：`operation=content.review`、Artifact/Task/Brief/GrowthPlan/四个来源 Artifact/ReviewIssue/ReviewerAuthority exact refs、`artifactContentHash`、`decision`、`returnStage`、`idempotencyKey` 与包侧 `requestHash`。ACCEPT 只能无 returnStage；RETURN 只能回到 `content_generation`；REQUEST_MORE 和任何 authority override 均拒绝。
- Artifact 复用 `public.aip_artifact` 唯一 Owner。Host 从同一行的 canonical metadata 读取完整 `ReadableContentArtifact` 投影，并逐项核对 Artifact exact ref、正文 content hash、Task/Brief/GrowthPlan、四个来源 Artifact、事实来源、商品、渠道、正文和约束核查；所有来源 Artifact 必须在 `aip_artifact` 中存在且 exact。调用方不能用命令正文覆盖 Owner。
- Task/Brief 复用 `public.aip_task`、`public.aip_brief_head`、`public.aip_brief_revision`。要求 Task 仍精确存在，Brief 是当前 `content_campaign` draft，且其 `spec.taskRef`、GrowthPlan、四来源 Artifact 与内容 Artifact 完全一致。
- ReviewIssue 复用 `public.aip_review_issue` 当前版本，按既有 canonical `ReviewIssueRevision` hash 算法重算；必须仍为 OPEN、subject Artifact id/hash 与本内容 Artifact 一致，RETURN 的 `return_stage` 必须为 `content_generation`。本切片不修改 Issue 状态或原 Artifact。
- `ReviewerAuthorityRevision` 当前没有独立 Owner 表。本切片不造影子表，而把它定义为现有 `public.aip_responsibility_plan_head/revision` 中当前、frozen、READY、COMPLETE、无 blocker 的 `content.review` 槽位及 assignee 的确定性只读投影。resourceId 固定为 `planId/content.review`，revision 等于 Plan revision，contentHash 对 `{responsibilityPlanRef,slotId,responsibilityType,requiredCapabilityIds,assignee,assigneeResolutionReceiptId}` 做 canonical hash；必须恰好一个当前 Plan 与调用方 exact ref 匹配。该 exact ref 只证明评审槽位分派，不代替 Agent/Capability 执行批准或外部发布批准。

## Receipt-first 与 feedback 原子性

- `ContentReviewReceipt` 使用既有 `ecommerce_growth_runtime_command_receipt` 作为 231-6 D2 指定的统一持久 Owner，不新增迁移或领域散表。receipt id 由 tenant、operation、idempotencyKey 的稳定 identity 生成；content hash 对去掉 `receiptRef` 后的完整响应 canonical hash，收据正文固定包含 requestHash、decision、五条 exact lineage、returnStage、首次 `replayed=false` 和两类零副作用。
- `execute` 先读取相同 idempotencyKey 的统一收据；存在时必须重验完整命令 hash、全部当前 Owner 和完整持久正文，随后用原正文继续 feedback enqueue，保持首次响应字节语义不漂移。首次时先通过 `BoundEcommerceGrowthRuntimeStore.put` 写入/回读收据，再由包内 `ContentReviewReceipt` 与 `ReadableContentArtifact` 构造确定性 `ResultFeedbackPlan`，在同一 HostTransaction 调用 `BoundEcommerceGrowthFeedbackPort.enqueue`。任一步失败由外层统一回滚，不能返回“评审成功但未登记回流”。
- feedback 的业务标题从已回读 Task title 获取，摘要从 Artifact body 取有界业务文本；二者继续经过 N7 业务文本校验。ACCEPT 固定三段，RETURN 固定一段；本切片只登记 pending outbox，不 claim/执行 target，不创建新 Task、不写 Memory/EffectReview、不调用 Provider、不结算费用。
- `verify_receipt` 从统一运行时表回读整份 ContentReviewReceipt，重算 receipt exact ref 并逐项等值；同时按确定性 command id 回读 `ecommerce_growth_feedback_command` 与 segments，要求 request hash、lineage 和不可变段正文完整等于包侧计划，不能只查 ID 存在。首次 enqueue 额外要求全部段为 pending/attempt=0；后续精确重放允许 7C worker 已合法推进 checkpoint，不把已回流误判成审阅漂移。

## 修改与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：新增严格命令解析、Artifact/Task/Brief/Issue/ReviewerAuthority Owner 复验、`ContentReviewHostService.execute/verify_receipt`、统一收据与 7C feedback 同事务接线，并纳入 exports；不改前八个 HostService 的业务行为。
- 修改 `services/aos-api/aos_api/ecommerce_growth_feedback_port.py`：只增加 transaction-bound 严格只读 command/outbox readback，供 content-review verify 使用；不改变 enqueue/claim/ack/recovery 状态机。
- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_store.py`：统一运行时 Receipt 只读显式绑定 `public` Owner，拒绝 TEMP/search_path 同名影子表；不改变写入函数或持久结构。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py`：覆盖严格命令、Owner/lineage、ReviewerAuthority 唯一投影、ACCEPT/RETURN、首次与精确重放、同 key 漂移、反馈缺失/篡改、Receipt 篡改、事务回滚、零副作用。
- 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_{feedback_port,runtime_store}_pg.py`：专用 PostgreSQL 连接改为读取既有 `AOS_EXTENSION_PG_*` 隔离参数，保留旧默认值，确保验证器不会绕回停用的本机默认实例。
- 用隔离迁移 PostgreSQL 验证真实统一 Receipt 与 feedback 表在一个事务提交或整体回滚、RLS/canary、重放唯一及正文篡改拒绝；累计回归 N7 content review/result feedback、7C port、runtime store/registry/HostPort、ContentGenerate、compile/diff、AR2 closure 和 memory validate，再做独立只读终审。验证通过后落 verification 证据、精确提交并同步 docs。

## 保留边界

本切片只形成内部内容审阅决定和待处理 feedback outbox；不修改 ReviewIssue，不改写原 Artifact，不 claim 或执行 feedback target，不创建 Task/候选/效果结论，不访问 Secret/URL/任意 SQL，不调用 Provider，不发布内容，不修改真实租户或共享业务数据库，也不启用生产 readiness seal。`org-org/dev-project` 仅用于隔离测试正例，`dev-org/dev-project` 仅作负向 canary；230 L0 继续挂起。
