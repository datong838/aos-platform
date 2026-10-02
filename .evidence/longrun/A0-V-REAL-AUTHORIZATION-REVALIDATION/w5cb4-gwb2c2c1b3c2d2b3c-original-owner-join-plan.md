# GW-b-2c2c1b3c2d2b3c｜原 Stage Owner 与生成消费者同事务联合

基线 `AOS-001129` / `m1 9b6cc63e`。先复习 231-5 §9、231-3 禁入、栖月汇统一 Task/Handoff、D-waves d2b3c。当前 `_review_receipt` 和 `_task_brief` 已能严格读取 accepted-stage v3，但 expected 尚未由原 Owner 产生；生成 `revalidate` 在最前面失败封闭。不能用 Receipt/Task.goal/Brief.spec 自身反推 expected。

本波目标：从同一租户、同一个 `HostTransaction` 内的原 `AnalystStageDecisionStore`、获批 GrowthPlan、Stage TaskRun/Plan/Attempt、Eval/permission，以及原 BI Occurrence/Case/Analysis Receipt 建立独立的 17 项 expected；再用它校验原 Review Receipt、Task/Brief。未完成可读 Artifact 与人工评审消费者前，生成 execute/Provider 与 Review Host accepted-stage execute 继续禁入。

文件级顺序：

1. `services/aos-api/tests/extension_runtime/test_analyst_stage_handoff_source_pg.py` 和 `test_ecommerce_review_task_brief_authority_pg.py`：先用可销毁 PG 的原 Owner producer 做 RED，断言当原决定撤销/过期、获批方案或 Artifact 漂移时，不得把 v3 Task/Brief 和 Review Receipt 视作可用。正例仅证明同事务原 Owner join；fixture 决定不是当前人工批准。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：复用 `ReviewAdvanceHostService` 已有 `_revalidate_accepted_stage_source`、`_revalidate_accepted_stage_runtime_sources`、`_revalidate_analysis_runtime` 和 `_revalidate_current_occurrence_case`，在 ContentGenerateHostService 中重建 expected 并交给现有两个读者；不复制 Owner 状态机、不放宽旧 Issue 合同。不具备完整生产者的 PG 正例不得用 mock 替代。
3. 跑专项与相邻回归、租户/过期/撤销/单原 Artifact 负例、py_compile 和 diff-check；API/Web 变更后重载并用 Codex 浏览器验收禁入态。verification 逐条标记已联合与未联合的原生产者，绝不把测试 PG 说成当前首链。

已知依赖：当前真实库八配置、正式 OIDC/Host 凭据、Growth1.13正式发布、assignment/binding 仍缺；这些只阻断当前实例。若原 Stage runtime/BI producer fixture 不足，本波先补原 producer 到真实 PG 的联合链，不通过手插 Receipt/假账号/手工 Run 填空。真实库只读、Host/worker/Provider 关闭；不读商城源、旧12 Run不重放、dev-org零写、230 L0挂起、不 push。
