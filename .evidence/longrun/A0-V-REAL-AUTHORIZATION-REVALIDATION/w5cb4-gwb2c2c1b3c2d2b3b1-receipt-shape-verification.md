# GW-b-2c2c1b3c2d2b3b1 原阶段 Review Receipt 形状验证

基线 `AOS-001127` / `m1 a5073009`；方案 `w5cb4-gwb2c2c1b3c2d2b3b-receipt-plan.md`。231-5 §9 要求 accepted Stage 与旧 Issue 来源分支独立，生成/评审共用同一原 Owner 链。

- RED：有效 accepted-stage 命令调用原 `_accept_receipt` 直接 `KeyError:'reviewIssueRef'`，1 failed/21 deselected，退出1。
- 最小改动：新分支先过原 strict 命令校验，Receipt body 明确 `sourceKind=accepted-stage-v1` 与完整17项 `sourceLineage`，不伪造 ReviewIssue/四 Artifact；原 Issue 分支字段位置/内容保持。`receiptRef.contentHash` 仍由完整 body 的 canonical hash 派生，改变 StageDecision 时 hash 改变。
- 专项/相邻：Review Host、v3 Task/Brief、生成 Handoff/预算五文件 83 passed、7 warnings，退出0；`py_compile` 和 `git diff --check` 退出0。测试只用可销毁 PG 与纯回执形状，当前真实库只读。
- 复审限制：新 Receipt **尚未由 Host execute 持久化**，内容生成 `_review_receipt` 也还不识别它；原 Stage Owner/BI/permission/获批 Plan 的实时复验依然由现有 revalidate 读取后禁入，不能把 shape/hash 测试当真人批准或真实首链。Host/worker/Provider 仍关。

下一项 d2b3b2：从原持久化 ReviewDecisionReceipt 读新分支，重算 hash，核 Handoff/Task/Brief/GrowthPlan、单 Artifact 与17项来源一致；再与原 Stage Owner/撤销/期限/租户联合，直到人工评审消费者齐备前保持执行门。
