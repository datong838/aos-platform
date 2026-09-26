# W5CB4 P2g｜同一原 Issue 的 exact ACCEPT 事件与 Host 子门

- 基线 `m1@889f4d19`，先补第八增量文件级方案；只扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。正式 `a0v_105` 一次性库沿同一原 TaskRun/settled Artifact/成功 StepRun/当前 EvalContract/通过报告/唯一 open Issue；未改生产库。
- 未决 open Issue 的 `ContentReviewHostService._issue_authority` 明确拒绝。测试 reviewer 通过正式 `AipProductionContractStore.resolve_review_issue` 提交 expected version、理由与原 Artifact exact resolutionRef，得到 resolved version 2；同幂等键 replay 回读原 Issue。独立 SQL 读回序号 2 不可变 resolved 事件、actor、exact Artifact ref 和唯一 `review_issue.resolve` Receipt。用 `review_issue_exact_ref` 形成新命令后，Host 的 `_issue_authority` 连同 `_issue_eval_authority` 在同库正式核通过报告、原 Plan gate、最新成功生成 StepRun、人类事件与 Issue 引用。
- 测试 actor `fixture-reviewer` 仅模拟正式公共 API 调用，不是栖月汇真实人工授权或当前工作台交互。此波只证明 Host 的 Issue/Eval 子门；尚无完整 `revalidate/execute/verify_receipt`、合法 TaskBrief/ReviewerAuthority、九操作 Host 锁、`content_review` StepRun/TaskRun 终态、反馈自动续跑或真实 Provider/商品事实。
- 专项 `1 passed, 6 deselected, 7 warnings`；内容、通用 EvalRunner 与邻近 PG 累计 `294 passed, 35 skipped, 7 warnings`；`git diff --check` 通过。纯后端隔离库，浏览器验收不适用。无商城源读取、旧十二 Run 重放、230 L0 推进或生产外呼。
- 下一波：沿原 resolved Issue 组成完整 ContentReviewHostService 的 TaskBrief、ReviewerAuthority、dispatch/Receipt 门，或把确切缺失权威列证后先完成独立的 `content_review` StepRun/TaskRun 内部续跑；严禁以本子门冒充自然业务闭环。
