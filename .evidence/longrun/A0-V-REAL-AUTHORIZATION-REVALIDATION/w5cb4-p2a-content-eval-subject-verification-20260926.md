# W5CB4-P2a｜可读内容 exact Eval 主体中间验证

## 结论

P2a 代码门 GREEN，**W5CB4 整波仍未完成**。既有 `AipEvalRunner` 原只接受媒体变体与 Agent 文字输出为评估主体；W5CB3 的 `ecommerce_content` 若走无主体 EvalReport，会让评估报告与待审正文脱钩。本次增加只有冻结 READY EvalContract 显式声明 `subjectKind=ecommerce_content`、`subjectInputMode=ecommerce-readable-content/v1` 才进入的新分支。

## RED→GREEN 与验收

- RED：合法 exact 内容 Artifact 主体被旧 runner 拒绝；缺显式协议仍会先读主体；内容输入 envelope 方法不存在。三项先失败后修复。
- 主体读取独立核 tenant、Artifact id/hash/type、原 Run 的最新 `content_generate` StepRun attempt/inputHash、元数据 `ecommerceGrowthContentArtifact` 的完整字段、正文/来源非空、完整 payload canonical hash 与 `artifactRef` 对齐；错租户、错 hash/类型、旧 attempt、空正文/来源失败关闭。
- 完整隔离库受控测试用公共 `AipTaskStore` 创建 Task/Plan/Run/StepRun/可读 Artifact，正式 `AipEvalRunner.run_by_contract` 把主体及 case 输入交给受控 target/judge，回读带 exact `subjectArtifactRef` 的 EvalReport，报告不含正文。没有模拟 EvalReport 入库，测试中的 suite/contract/gate policy 则是隔离 fixture，**不是当前已批准的生产资产**。
- 专项与邻接累计 **49 passed，7 既有 warnings**；`compileall`、`alembic heads=a0v_104`、`git diff --check` 通过。无 UI 改动，浏览器验收不适用。无生产迁移/Worker/Provider 启用、商城源读、旧 Run 重发或 push。

## 尚缺

当前 `EvalGatePolicyRef` 的名义类型仍是 `MediaGatePolicyRevision`，不能把 fixture policy 当真实内容批准；正式内容 EvalContract/Suite/Policy 尚未注册/证明。ReviewIssue 尚未由报告自然建立，人类待办、Review Receipt、TAOR Run 终态和反馈自然续跑均未完成。下一步先补“ReviewIssue 只能绑定同 exact 内容 Artifact 的正式 EvalReport”校验与创建/待办路径，再做界面及 Run 终态。
