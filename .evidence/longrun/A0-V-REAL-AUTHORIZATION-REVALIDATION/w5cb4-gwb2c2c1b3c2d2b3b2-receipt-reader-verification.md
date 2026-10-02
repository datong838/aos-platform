# GW-b-2c2c1b3c2d2b3b2 原阶段 Review Receipt 读者验证

基线 `AOS-001128` / `m1 b7b7b23b`；方案 `w5cb4-gwb2c2c1b3c2d2b3b2-receipt-reader-plan.md`，遵循 231-5 §9 与栖月汇统一 Task/Handoff。

- RED：新来源调用原 `_review_receipt` 参数不支持 `source_kind`，1 failed/22 deselected，退出1。
- 新分支只接受明确 `accepted-stage-v1` 和由调用方提供的 17 项 expected（含 internal markings）；在同租户查询的唯一 Receipt 行上核精确字段、request/body/target hash、ACCEPT/无外部效果、Handoff/Task/Brief/GrowthPlan、单原 Artifact 与 Stage 源身份。旧默认只接受旧 ReviewIssue/四 Artifact 回执。
- 读者合同正反：有效 v3 回执、篡改 `markings` 但未重算 hash、独立 expected TaskRun 漂移、来源 Artifact 漂移；测试使用有界事务替身，未构造当前真实业务通过。Review Host/TaskBrief/生成相邻五文件 84 passed、7 warnings，退出0；补 internal 标记门后专项2 passed；py_compile、git diff --check 退出0。
- 一致性/风险：目前 accepted-stage Host execute 仍关，真实库该新 Receipt 零行；读者尚未由原 Stage Owner 的独立 expected 调用，也未接可读 Artifact/人工评审消费者。此为代码合同，不是正式人工批准或自然首链。当前真实库只读、Host/worker/Provider不启，dev-org无写、旧Run无重放。

下一项 d2b3c：在同事务用原 StageDecision/TaskRun/Plan/Attempt/Eval/Artifact/permission、获批 GrowthPlan 和当前 BI 来源产生独立 expected，接新 Receipt 读者与 v3 Task/Brief 读者；继续原生产者 PG 联合链及人工评审。正式 OIDC/八配置/正式发布/Host assignment 独立补齐。
