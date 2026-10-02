# d2b3c4g1｜原阶段内容评审 Eval/人工 Owner 读者接线计划

## 上位合同

231-5 §9 的已接受阶段来源必须保持原 StageDecision、获批 GrowthPlan、原单 Artifact 与 v3 Task/Brief 同源；生成后的内容评审另需内容专属 Eval/ReviewIssue、独立真实人工 ACCEPT/RETURN。BG00gw d2b3c4f 已在 revalidate 回读原 Stage、持久 Review Receipt、v3 Brief 和内容 Artifact，但在内容 Issue/人工事件检查前固定禁入。当前 G2 正式 Skill Eval/原 Analysis producer 缺失，不能用 fixture 解除执行门。

## 精确改动

1. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：仅在 `ContentReviewHostService.revalidate` 的 `accepted-stage-v1` 分支，复用现有 `_issue_authority`（其内含内容 Artifact、EvalReport、原内容 Eval gate、attempt/最新尝试与人类 Issue 事件检查）和 `_reviewer_authority`（当前 frozen 责任槽与事件 actor 精确一致）。顺序为可读 Artifact→原 Stage/Review Receipt/v3 Brief→内容 Issue/Eval→人工 reviewer→GrowthPlan hash→保留 `Host is not wired`。旧 Issue 分支及 execute/verify 不动。
2. `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py`：使用既有原 StageDecision/GrowthPlan disposable PG producer；Stage/Brief 读者局部测试 seam 后，用真实 PG 证缺内容 ReviewIssue 失败封闭。seam 只用于验证后续读者顺序，不作正式持久 Receipt 正向证明。
3. `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py`：RED 证明 accepted-stage revalidate 在原 Stage reader 后调用内容 Issue 与 reviewer，任一拒绝不写 Receipt/反馈；execute/verify 仍在 DB 前禁入。测试只证明接线和负向，不声称当前业务通过。

## 验证与风险

先新增 RED（原路径绕开 Issue reader，期望失败），再最小接线；跑上述专项及相邻生成/评审测试、`py_compile`、`git diff --check`；若页面适用，刷新 `/aip/skill-publish` 只读截图证明现行禁入。当前真实库只读，Host/worker/Provider 关闭。剩余仍包括原 G2/Analysis producer、真正持久 Review Receipt 联合正向、内容 Eval/Issue 与独立人工事件生产者、执行回执及自然首链。局部 test seam 绝不算生产者证明。
