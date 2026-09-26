# W5CB4 P2d 第一段｜正式生成步骤的只读来源证明

- 状态：局部代码门 GREEN；尚未认领或完成任何生产 StepRun，W5CB4 未完成。
- 方案：`w5cb4-content-review-taskrun-feedback-plan-20260926.md` P2d。先从原始已提交内容结果、预算、Provider/Usage 独立读回建立唯一原 Run/Artifact 绑定，再由下一段公共 AIP Store 事务化 TAOR。
- RED：`test_ecommerce_content_step_source.py` 首跑因尚无 `ecommerce_content_step_owner` 而在收集阶段失败；未把它算成业务验证。
- 最小改动：新增 `ContentGenerationStepSource.read`；只接受状态 Reader 独立返回 `COMPLETED` 且预算 `settled`，核原 Journal 命令 Task、原 ContextReader Run、invocation 确定性 Artifact ID/source、同租户正在执行的 Task/Run 和已批准的 `content_generate→content_review` Plan。返回不可变 proof；此 proof 本身不授权执行。
- 专项/邻接回归：新源证明、原内容执行组合、内容 Eval、内容 Review Host 共 `20 passed, 7 warnings`。未改 UI、未启 worker 或 Provider；此段无需浏览器验收。
- 风险/下一段：当前无正式 StepRun Owner、当前安装 fence 与提交未知冻结的完整代码，因此不得称内容自然产物可评估。下一段在同事务里复核安装与 proof，调用公共 `AipTaskStore` claim/TAOR/complete_step，提交后独立读回；任何失败不得重发 Provider。
