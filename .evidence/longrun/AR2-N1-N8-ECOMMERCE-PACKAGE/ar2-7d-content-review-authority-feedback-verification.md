# AR2-7D Content Review 权威与反馈同事务验证

日期：2026-09-09  
基线：`m1@a6c426c2`  
结论：`CONTENT_REVIEW_RECEIPT_FEEDBACK_ATOMIC_GREEN`

## 实现结论

- 固定第九项 `ecommerce_growth_content_review` 已具备显式 `ContentReviewHostService.revalidate/execute/verify_receipt`，严格消费 N7 `content.review` 命令，不接受 REQUEST_MORE、错误 returnStage 或调用方 authority override。
- 内容 Artifact 从 `public.aip_artifact.metadata.ecommerceGrowthContentArtifact` 读取完整业务投影；Artifact、四个来源 Artifact、Task、当前 TaskBrief、GrowthPlan lineage 与 OPEN ReviewIssue 均从现有 Owner 同事务回读。正文、商品、渠道、事实来源和约束继续执行中文业务文本与 exact closure 校验。
- `ReviewerAuthorityRevision` 没有新增表。它是当前 frozen/READY/COMPLETE ResponsibilityPlan 的 `content.review` 槽位只读投影；Host 按 resourceId 定位唯一 Plan，`FOR SHARE` 锁定 head/revision，并要求 raw JSON、typed DTO、持久 content hash 三者一致后才生成投影 hash。它只证明槽位分派，不等同 Provider、发布或外部业务批准。
- `ContentReviewReceipt` 复用 `public.ecommerce_growth_runtime_command_receipt`。首次调用先写并精确回读完整收据，再在同一 HostTransaction 登记 AR2-7C feedback command/segments；任一步失败整体回滚。ACCEPT 固定三段，RETURN 固定一段，首次均为 pending/attempt=0；后续重放允许合法 checkpoint 已推进，但 immutable command 与 segment payload 必须完全相同。
- `verify_receipt` 同时核对统一 Owner 的完整 command hash、完整响应、确定 receipt ref 和 feedback immutable readback。所有关键 JSON 比较均用 canonical serialization，`revision/sequence=1 -> true` 不再能利用 Python 相等绕过。
- feedback target reader 在本 Host 中固定拒绝调用；本切片只 enqueue，不 claim/ack/reconcile 或执行 EffectReview/Memory/Task target。运行时 Receipt read 与 feedback readback 显式绑定 `public` schema，TEMP/search_path 同名对象不能充当 Owner。

## 测试证据

- ContentReview/feedback/runtime/registry 聚焦：`37 passed`。
- 新增 ContentReview 专项覆盖 ACCEPT/RETURN、Receipt-first 精确重放、完整 command 漂移、feedback 缺失、Receipt/segment 篡改、布尔冒充整数、ReviewerAuthority 唯一槽位、Artifact 与 ReviewIssue raw Owner、真实 PostgreSQL 同事务提交和 feedback 失败整体回滚。
- 扩展运行时全量：`717 passed, 471 skipped`；skip 均为需要显式环境开关的既有专用套件。
- 显式专用 PostgreSQL：在 `127.0.0.1:18434`、一次性数据库上运行 feedback/runtime-store PG 套件，`7 passed`。两个旧套件改为读取既有 `AOS_EXTENSION_PG_*` 参数并保留旧默认值；验证期间未连接共享业务数据库。
- Python compile：通过。
- `git diff --check`：通过。
- AR2 closure：`scannedPythonModules=1707`、`classifiedModules=91`、`migratedModules=57`，五类错误数组均为空。
- memory validate：`GREEN`，`project_revision=AOS-000571`，delivery/task/event=`865/846/2226`。

## 独立复审

首轮只读复审发现四个 blocker：ReviewIssue raw JSON 未严格对账、ResponsibilityPlan 未锁 head/未对账 raw hash、feedback/Artifact 使用 Python equality、verify 未绑定完整 command。四项均修复并增加反例。第二轮确认无剩余 blocker；未发现生产 readiness seal 被修改或新增外部副作用。

## 文件摘要

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：`c6dee8b8656c1191cca9be61856b7dfedf1e79989cc9d13747810fdc865b7dbc`
- `services/aos-api/aos_api/ecommerce_growth_feedback_port.py`：`0f90af8387eb500d0360108699f87a370ceeeca0de4f22994246dffaaac7ff09`
- `services/aos-api/aos_api/ecommerce_growth_runtime_store.py`：`bc1814c4b6016cbc13308978d4535574eb54e0f290e5b063d59e83239a81b8bb`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py`：`2f1b32d9211daa0d4226bb18d999d0512bb85cd2a9bf69d87c6bb9b6b6d43413`

## 边界与下一步

本切片没有生成内容、调用 Provider、解析 Secret、结算费用、修改 ReviewIssue/Artifact、执行 feedback target、发布内容、迁移生产库或写真实租户数据。ContentGenerate 仍只有确定性 `FAILED_NO_EFFECT`，因此本次 PostgreSQL 正例以隔离测试数据证明事务合同，未宣称真实生成内容已进入评审。下一施工项按 AR2-7D 清册检查九项整组 runtime readiness/cutover 的剩余退出条件与端到端 no-effect 纵向验收；230 L0 继续挂起。
