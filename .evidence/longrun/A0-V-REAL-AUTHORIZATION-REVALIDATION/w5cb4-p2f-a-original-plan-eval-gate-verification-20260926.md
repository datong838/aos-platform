# W5CB4 P2f-a｜原批准 Plan 的内容 Eval 门（部分代码门）

## 当前权威

- m1 基线 `810da8f0`；方案先行，未 push。上位依据为 231-5 首链人工评审、231-9 BG-04 与栖月汇产品方案的 exact 来源/策略/版本约束。
- 只读指定元库 `aos_meta_head`：Alembic `a0v_092`，`org-org/dev-project` 内容主体 EvalContract=0。C06 Skill r2/r3 已发布但只见 Skill 治理 Suite `ecommerce.skill.C06.contract.v1@1`；不得冒充内容 Artifact 的 Eval。

## RED→GREEN

- RED：已有同主体 EvalReport/Artifact/StepRun 的 Host 在原 Plan 的 `content_review.gateRefs=[]` 时仍接受，测试实际为 `Failed: DID NOT RAISE ValueError`。
- 新 `ecommerce_content_eval_plan_gate.py` 用租户作用域的原 TaskRun→原 Plan→Task join 回读；要求 Plan 为当前 approved，且唯一 `content_review` 步骤有唯一与报告合同 ID/revision/hash 完全一致的 `EvalContractRevision` gate。拒绝无门、重复、错类型/hash、草稿、被新 Plan 替代、错租户。公共 ReviewIssue 内容入口和 ContentReviewHost 都调用同一门；不新增审批表、不写 Run/Plan。
- 正向隔离 PG fixture 在 Plan 批准前已有 exact gate，内容 EvalReport→ReviewIssue→Host 通过；反向与邻近累计 `104 passed`，`git diff --check` 待提交前复核。无 UI 改动，不适用浏览器验收。

## 尚未完成

- 本段仅防止报告绕过原 Plan，并未产生正式内容 Suite/Contract，也未改变 `ContentTaskRunOwner` 的新 Plan 构造；当前实例没有合法内容审核合同，故没有可启用的自然评审链。生产迁移/Worker/Provider 未启，商城源与旧 12 Run 未触碰。
- P2f-b：建立正式内容审核包的当前权威与 Plan 创建前绑定；之后才做已结算 Artifact 的待办/人工决定/Run 终态。不能用 fixture 或 C06 Skill 治理报告补票。
