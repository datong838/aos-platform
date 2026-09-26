# W5CB4 P2c 前置｜ContentReview Host 对历史 Issue 重验内容 Eval

- 状态：局部代码门 GREEN；W5CB4 整波、正式内容 Eval 激活、待办 Owner、TaskRun 终态和自然反馈仍未完成。
- 依据：`w5cb4-content-review-taskrun-feedback-plan-20260926.md` P2c 前置补洞；P2b `30867523` 仅限制新建 Issue，Host 不能信任历史 Issue 一定经该新门。
- RED：`test_content_review_rechecks_exact_issue_eval_subject_and_attempt` 首跑因 Host 无校验入口失败；此前已有人类决策事件测试仅验证 Issue 本身。
- 最小实现：Host 按 Issue 所存 EvalReport ref 同租户回读 immutable 报告，核 content_hash、exact 内容 Artifact ID/hash、原 Run 的 `content_generate` StepRun ID/attempt/inputHash、合同/政策 ref 形状。ACCEPT 要求报告 attempt 仍为最新；RETURN 保留原报告 attempt，并继续由既有人工事件/ReturnDecision 确认新返工目标，避免误拒合法退回。无独立审批状态或第二报告来源。
- 验证：正式隔离库的 AIP EvalReport→内容 ReviewIssue→Host 再读路径通过；错主体、缺政策、畸形 attempt、ACCEPT 旧 attempt 失败关闭，RETURN 新 attempt 不误拒。内容评审、生产合同与 Issue 邻接回归 `35 passed, 7 warnings`；`compileall`、`git diff --check` 通过。无前端改动，本小段无浏览器验收。
- 边界：本段不证明 EvalContract/Suite/Policy 已有当前生产激活，也不证明人工真实决策或自然 Run 终态；无商城源读、Provider 调用、生产写入或旧 Run 重发。下一步继续已计划的当前 Eval 权威/只读待办 Owner。
