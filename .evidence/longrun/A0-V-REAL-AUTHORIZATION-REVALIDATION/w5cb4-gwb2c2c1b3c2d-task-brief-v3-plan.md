# GW-b-2c2c1b3c2d｜原阶段来源至 Task/Brief v3 施工方案

基线：2026-10-02，`AOS-001121`、`m1 b1d7bf5b`、当前权威库 `aos_current_preview_20260927@a0v_135`。已复习 231 主计划、231-5 §1/§9、栖月汇六同事统一 Task/Handoff 产品方案、BG00GW 清单及原 Handoff/Task/Brief/内容生成/评审代码。当前实例 OIDC/Host 身份、assignment、八候选、Growth1.13 正式发布/绑定缺失，保持禁入；本波只在一次性测试库写测试数据，当前真实库只读。

## 最终合同与顺序

原 Issue 分支仍为四个 `ArtifactRevision`、ReviewIssue、Brief v1/v2。`accepted-stage-v1` 只使用原 `AnalystStageDecisionRevision(accept)`、原 TaskRun/Plan/StageAttempt/EvalReport/Artifact、责任计划及获批 GrowthPlan；不能补造 ReviewIssue 或四个 ArtifactRevision。命令的 `requestHash` 已覆盖全部 exact refs。新的 Handoff hash、Task.goal、Brief.spec 要携带同一 `sourceLineage`（来源种类、cutoff/expires、Occurrence/Case/BI Run/Analysis Receipt/Plan、GrowthPlan、Eval、Stage Decision/TaskRun/Plan/Attempt/Artifact/ResponsibilityPlan），Brief schema 固定 v3，单原 Artifact 保留为一项 `artifactRefs`。同一 idempotencyKey 跨分支/来源变化必须由原 Task/Brief Owner 拒绝。

此波先完成 **v3 持久化来源骨架**，再接生成和评审双消费者，最后才可解除 Host execute/Receipt 禁入。不能因前一段通过就把 `handoff_pending` 标 GREEN；只有下游同源复验、原生产者 PG 联合正反链、自然当前实例合法身份和配置均通过才能宣布首链。

## 文件级 RED、实现、验证

1. `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py`：用现有原 Owner 的 disposable PG 事务，在直接调用前先通过既有严格 parser 验证 accepted-stage 命令；RED 预期当前 `_review_lineage` 因强取 `reviewIssueRef` 拒绝。正向断言原 Task Store、Brief Store 的 v3 schema、Handoff/Task/Brief 同一来源 exact refs、hash、单原 Artifact，replay 相同结果与 rollback 零行；反向同 key 篡改 Stage Decision/Artifact 不能覆盖原持久化结果；旧 Issue v1/v2 用原测试保持兼容。这是**结构/Owner 写入测试**，测试命令不是当前真人批准，不构成 Host 授权。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：只改 `_review_lineage` 的来源分支与共同 Owner 写入，使 accepted-stage 构造上述 v3 内容；旧分支字节级结构不变。Host `revalidate` 仍在完整来源读取后失败封闭，`execute` 仍拒绝，`verify_receipt` 仍返回空；不启自然执行。
3. 下一段同一登记任务：在 bundle 的 `ecommerce_content_campaign_workflow.py`、`content_artifact_review.py` 及宿主对应生成/评审读者新增 v3 来源歧视和原 Owner 同源复验，旧四引用路径不变；跨来源/撤销/过期/跨租户负例优先。双消费者齐备后另做隔离 PG 生产者联合正反链，才能评审解除 Host 禁入。若本轮无法完成双消费者，verification 明确 d1 仅来源骨架、登记 d2 的精确文件，绝不伪称完成整个 d 波。

专项先跑新增 PG 测试与旧 `test_ecommerce_review_task_brief_authority_pg.py`，再跑 Review/生成相邻回归。需要的 PG 只创建 `aos_test_*_ti4_test` 并自动删除；运行前核 DSN 指向该测试库的管理实例，严禁对当前库执行写测试。最后 `py_compile`、`git diff --check`、方案/代码一致性检查、verification、m1 精确提交和 AOS/Prime/D-waves 更新。前端未变，本段浏览器只复核当前禁入状态，不把页面200当业务通过。
