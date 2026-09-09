# AR2-7D Content Generate Receipt-first 无 Provider 执行方案

基线 `m1@15a876d8`。当前 `ContentGenerateHostService` 已在同一 HostTransaction 内闭合 Review/Handoff、Task/Brief、GrowthPlan、四类 Artifact、事实来源、职责、Capability、ModelRoute/Pricing/Approval/Budget/Capacity、Binding 及其 dependency Owner，但仍只有 `revalidate`，不能满足固定 HostService 的 `execute/verify_receipt` 合同。本切片复用已封板 AR2-7A Store，形成一个可持久回读且没有 Provider 请求的确定性 `FAILED_NO_EFFECT` 结果。

## 状态与原子性

- `execute` 使用 `TransactionBoundConnectFactory` 把 `AipBudgetReservationStore` 绑定到外层已锁定 HostTransaction；以 ContentGenerate 的 operation、idempotencyKey、Task、Budget、Pricing、Approval、CNY 与 upperBoundFen 构造唯一 ReserveBudgetRequest。
- 首次执行在同一外层事务内先写 CapabilityInvocation=`prepared` 与 BudgetReservation=`held`，随后走 7A 允许的 `HELD -> RELEASED` 确定性无 Provider 分支，并把 invocation 推进为 `failed`。外层只有在领域 Receipt 回读和统一 runtime Receipt 都成功后才提交，所以失败不会留下半笔预留。
- 返回 N7 固定 `FAILED_NO_EFFECT` 形状：CapabilityInvocationRevision 与 BudgetReservationRevision 均引用最终 revision；Provider request/result、Usage、Artifact 和实际费用为空；retryDirective=`RETRYABLE_NO_EFFECT`；五类副作用计数全为零。
- 相同 operation/idempotencyKey 与相同预算请求由 7A Store 精确重放；已有统一 runtime Receipt 时先按完整命令 hash 与 command requestHash 核对，再回读 7A Owner 并返回首次持久正文，保持 `replayed` 等字段也不漂移；命令或预算请求漂移均冲突。`verify_receipt` 从同一事务按 reservation exact id 回读完整 7A 状态，重建返回正文并逐项等值；不能只凭调用方 Receipt 或 ID 存在放行。

## 修改与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：补齐 ContentGenerate 的 transaction-bound 7A execute、完整 Receipt 投影和领域回读 verify；不改其他八个 HostService。修改 `services/aos-api/aos_api/aip_budget_reservation_store.py`，让 7A 自有表与 authority 表统一使用经白名单校验的显式 schema（生产默认 `public`），并让完整 Owner 回读复算 invocation/reservation hash、状态和 Provider receipt 不存在性，拒绝 TEMP/search_path 影子表与摘要行篡改。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_receipt_first_no_effect.py`：覆盖首次 reserve/release、精确重放、key 内容漂移、预算不足回滚、Receipt 字段/引用/状态漂移、布尔冒充整数、同事务调用与零 Provider 路径；用隔离迁移 PostgreSQL 验证真实 7A 表和三桶最终不占额，并覆盖同名 TEMP 影子表及 invocation/reservation Owner 篡改拒绝。
- 回归全部 ContentGenerate、7A Budget、HostPort/runtime Store、Review/Binding 邻接；执行 compile、diff check、AR2 closure、memory validate，再做独立只读终审。验证通过后落 verification 证据、精确提交并同步 docs。

## 保留边界

本段刻意不调用 `submit`，不生成 `CapabilityProviderRequestReceipt`，不解析 Secret，不调用、重试或对账 Provider，不创建内容 Artifact，不结算 Usage/费用，不推进 AgentRun/CapacityReservation，不发布或改写经营数据。它证明无 Provider 条件下 receipt-first 的确定失败与可重试语义，不声称内容生成成功，也不把 ContentGenerate 加入生产 readiness seal。真实或隔离 Provider 跨事务执行、COMPLETED/UNKNOWN 恢复路径与 ContentReview 仍属后续施工；230 L0 保持挂起。
