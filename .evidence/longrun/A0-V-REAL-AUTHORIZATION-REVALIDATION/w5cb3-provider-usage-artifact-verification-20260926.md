# W5CB3｜Provider intent、measured 用量与可读内容产物代码门验证

## 结论

`W5CB3_CONTROLLED_PROVIDER_TO_READABLE_ARTIFACT_CODE_GATE_GREEN_REAL_CONTENT_PENDING`。现有正式 `CurrentContentRunner`／`ContentExecutionWorker`／`ContentResultConsumer`／`ContentUsageRecorder` 在默认关闭状态下已有唯一 ProviderRequestReceipt、提交后外呼、结果 Journal、measured Usage、预算结算和 Artifact Owner；本波修复测试合同漂移并新增同库组合证明。**未开启生产 Provider，未发生真实内容生成或业务闭环。**

## 方案／代码对账

- 上位 231-5 §1/4/6/7、231-9 BG-04 要求当前审批/预算/来源/安装重验、唯一外呼、实际用量与可读草稿；`PENDING` 不是内容完成。W5CB2 exact 命令仍经 `CurrentContentPreparation` 当前权威重验后才能提交；本波不放宽该门。
- RED：隔离 PG 的旧 selector 夹具把 Runtime Receipt `request_hash` 写成命令内层 `requestHash`，而正式 Host/Journal 合同要求 `sha256:`＋完整命令 JSON hash，致 2 项失败。仅修复测试夹具两个写入点，未修改生产校验。
- 新同 schema 测试用 `ContentBudgetCommandOwner._command_envelope` 产出 exact 命令，给正式 PENDING selector、预算 Worker、受控无外网结果、结果 Consumer 和独立 StatusReader；读回唯一 ProviderRequestReceipt、两条 UsageReceipt、预算 `settled`、正文/商品名 Artifact，重跑不重发，`dev-org/dev-project` 零结果。受控 Provider 响应来自既有 in-memory transport，不是外部真实调用。
- 现有单项测试另覆盖提交前当前权威失败不提交、Provider timeout→unknown 不重发、结果持久化失败不重发、账本事务回滚、缺 Artifact 读回不报完成、开发费用 `cost_pending`。未用测试替代生产当前批准。

## 验证与边界

- 本波专项与邻接累计隔离 PostgreSQL **58 passed，7 既有 warnings**；先前修夹具后 31 passed；`alembic heads=a0v_104`、compileall、`git diff --check` 均通过。测试 PostgreSQL 容器 `aos-w5cb3-test-pg` 已停止并 `--rm`。无 UI 改动，浏览器验收不适用。
- 夹具是同一随机 schema 的公共表子集，**不是完整生产 schema／真实 Handoff→容量→预算全链**。此前 W5CB2 完整夹具欠账仍是激活硬门；生产迁移未应用，Worker 与 Provider 仍关闭，当前安装/审批/来源/价格/容量/权限及独立 Receipt 尚未现场证明。没有读商城源，没有重播旧 12 Run，没有手工 `run_definition`，无 push。

## 下一波

W5CB4 接可读 Artifact 后的人工 exact Review、内容 TaskRun 终态和反馈自动续跑；并在正式激活前补完整同库 Handoff→容量→预算→Provider→Artifact 夹具与当前真实权威。不可把本波绿门称为首链自然成功。
