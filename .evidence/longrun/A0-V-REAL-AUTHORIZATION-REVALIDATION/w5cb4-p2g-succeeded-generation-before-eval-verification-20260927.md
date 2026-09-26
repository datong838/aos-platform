# W5CB4 P2g 第 2 段｜生成 StepRun 正式成功后才可进入内容 Eval/评审

- 上位与计划：231-5 内容生成→结构/来源 Eval→人工评审顺序；`w5cb4-p2g-content-subject-eval-review-pending-plan-20260927.md`。本段不生成新内容、不跑 Provider、不接真实待办。
- RED：既有内容 Eval 正向夹具原来在刚 claim 的 `content_generate` StepRun 上跑主体评估。新增断言先证实 Runner 接受了未完成 attempt；又分别证实公共 ReviewIssue 内容校验与 Host 会读过未成功步骤。
- GREEN：`AipEvalRunner` 仅对 `ecommerce_content` 主体要求其原生成 StepRun `status=succeeded`；正向夹具先通过四相 TAOR/`complete_step` 再评估。公共 `create_review_issue` 内容分支和 ContentReview Host 对同一最新生成 attempt 复核 succeeded，旧报告/绕行入口也不能利用未完成步骤进入人工决策。媒体/文本旧语义不变。
- 专项内容 Eval/Host 正反测试通过；内容＋通用 EvalRunner 累计 `276 passed, 9 skipped, 7 warnings`。`git diff --check` 通过。9 skipped 为专用 PG opt-in，不当作真实当前实例验收。无 UI 变更，浏览器验收不适用。
- 当前生产实例仍 `a0v_092`、无正式内容主体权威；这是隔离代码门，不是自然首链 GREEN。下一段是只读待办候选；必要条件仍包括当前安装、原批准 Plan exact gate、已结算 Artifact、最新 succeeded 生成 attempt 和同主体正式通过报告。无合法候选返回空，不伪造报告/Issue。
