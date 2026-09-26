# W5CB4 P2g 第 1 段｜失败结构预审不得 ACCEPT

- 依据 `w5cb4-p2g-content-subject-eval-review-pending-plan-20260927.md`；只补内容评审 Host 的既有漏洞，不称待办或自然首链完成。
- RED：已有 `_issue_eval_authority` 对同主体、attempt、原 Plan exact gate 进行核对，但未读取 `gate_passed`；失败报告仍可走 ACCEPT。新增同一测试中的失败报告 ACCEPT 反例先失败。
- GREEN：从持久 EvalReport 读取 `gate_passed`；内容 ACCEPT 只有 `True` 可继续，失败报告保留人工 RETURN 路径。不更改 ReviewIssue 公共表、媒体/文本路径、既有人类角色/事件和原 Plan 校验。
- 专项 1 passed；内容邻近累计 `268 passed, 9 skipped, 7 warnings`；`git diff --check` 通过。无 UI 变更，浏览器验收不适用。9 skipped 为专用 PG opt-in，不能算真实实例验收。
- 当前实例仍 `a0v_092` 且没有内容主体合同/真实 Artifact 报告；本段仅是默认关闭的代码门。下一段才做已结算 Artifact、最新生成 StepRun、原 Plan exact gate、同主体正式通过报告的只读待办候选；无合法候选返回空，不建 EvalRun/Issue。
