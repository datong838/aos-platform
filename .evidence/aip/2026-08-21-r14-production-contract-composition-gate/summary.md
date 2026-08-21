# R14 生产契约组合门 EvidencePack

状态：`GREEN_WITH_WARNINGS`。

本波没有重写服务端 ProductionStart 事务门，也没有创建 Proposal、审批、Lease、TaskRun、AgentRun 或 Provider 调用。最小改动只补齐 canonical ActionProposal 的 `impactPreviewRef` 严格解析，以及生产契约页的合法 Proposal 筛选和 exact ref 自动提交。

真实租户 `org-org/dev-project` 当前有 1 条 ActionProposal，但它是 drafted、已过期、无 Task 且无 ImpactPreview ref；页面在选择真实 Preview 后诚实显示“无同 Task、同 exact Preview、approved、未过期候选”，Start 按钮保持关闭。负向租户 `dev-org/dev-project` 返回 0 条 Proposal，没有泄露真实租户数据。

验证结果：前端专项 16 passed、TypeScript GREEN、Web 累计 198 files / 2008 tests、后端 W2-D 25 passed、`git diff --check` GREEN。浏览器证据见同目录三张截图。

本 Receipt 不解除 Workshop 的 B5、SourceReadiness 和同-cutoff EvidencePack 三项外部阻断，也不授权 Workshop W2-00B、Provider 调用、AgentRun 或生产 Action。
