# AR2-7D Content Generate Route / Price / Budget / Approval 权威验证

基线 `m1@e35ba59e`。本段按 `ar2-7d-content-generate-route-budget-approval-plan.md` 完成 ContentGenerate 的 ModelRoute、Price、Budget 与 Approval 前置权威复验；未增加 execute/verify，未创建 reservation/invocation，未加入 readiness seal。

## 实现核对

- `ContentGenerateHostService` 在既有 Handoff/Task/Brief/GrowthPlan/Artifact 与 Agent/Responsibility/Capability 复验后，共享锁定 tenant 当前 ModelRoute head；要求 current revision/version、ACTIVE、TEXT -> TEXT、当前 Capability，并按 ModelRuntime 发布口径复算原始 payload 摘要。摘要之外的原始 tenant/revision 也必须与 scope/exact ref 一致，`revision: 1 -> true` 失败关闭。
- Price、Budget、Approval 使用同一数据库 `clock_timestamp()` cutoff。Price 按 ModelRuntime meta 排除口径复算正文摘要，并核对 tenant、ID、revision、contentHash、lifecycle、CNY 与有效期；Budget 延用 7A active/effective/exact 判定。
- Approval 先核 immutable ApprovalEvent exact hash，再读取原 `AipActionStore` 写入 `aip_action_draft.snapshot` 的 stable Proposal 正文，复算 proposal hash，并对 JSON 子树做 canonical hash 等价、对标量逐项对账 Proposal 行的 action、Task、payload、policy、binding、来源、创建者与 expiry。批准额度直接取 stable payload 且要求严格整数；只修改 `budgetUpperBoundMinor`、用 `true/1` 伪装相等或修改其他正文并保留旧 proposal/approval hash 均失败关闭。
- Owner 查询生产默认限定 `public.`；可注入的 `authority_schema` 只接受小写 SQL 标识符白名单，供专用 PostgreSQL 隔离 schema 使用，不改变生产默认 Owner。
- 实现摘要：`ecommerce_growth_runtime_adapters.py` = `5e250b2ee30b8281a4b262360caacbcb6d9b628c65d269226ba1f0f8233dd6d1`；`aip_budget_reservation_store.py` = `d364e53379550ab157df113b257dde63d2f557e6dee40f85ada1a891eaef4120`。

## 验证结果

- Route/Approval 聚焦测试：`16 passed, 7 warnings in 3.61s`，覆盖 Route current/hash/lifecycle/modality/capability、tenant 漂移、布尔 revision、ActionStore stable snapshot 正例与 Proposal payload 篡改反例。
- 专用 PostgreSQL + 聚焦：`23 passed, 7 warnings in 4.62s`，使用 `127.0.0.1:18434/aos_test_admin` 隔离库；覆盖 Proposal/Price 正文被改而保存 hash 不变、stable `true` 与 Proposal `1` 伪相等时失败关闭、public/TEMP schema 隔离、并发与原 7A 状态机回归。
- 扩大回归：全部 ContentGenerate、Review 邻接、Budget contracts/PG、ModelRuntime contracts/resolver/store 合计 `135 passed, 7 warnings in 5.14s`。
- 首次聚焦命令漏设既定隔离 DSN，测试框架在默认 `127.0.0.1:5433` setup 连接拒绝、零测试执行；补齐 `AOS_DATABASE_URL` 后通过，未改生产逻辑。
- `git diff --check` 与目标 Python 编译通过。
- AR2 closure：`1707 / 91 / 57`，`hashErrors`、正反向未分类依赖、跨层 import、dynamic reference 五类数组均为空。
- memory validate：`AOS-000571 / GREEN`，Delivery Receipt `865`、event `2226`、task receipt `846`。
- 独立只读终审连续发现 Route metadata、Proposal stable 正文和 Python `bool == int` 三项完整性阻断；逐项补强并加入反例后，第三轮复核确认无剩余 blocker。终审边界同样确认本段不证明 Route/Model/Price/Capacity 完整执行 tuple。

## 边界与下一项

本段不读取 Secret、不解析/选择或调用 Provider、不创建 CapabilityInvocation、BudgetReservation、CapacityReservation 或 Artifact，不改变预算 bucket，不产生费用、审批、发布或业务副作用。Route 候选仍未与 exact RegisteredModel、Provider、Price、CapacityReservation 和 AgentRun 组成同一执行 tuple；下一段继续 Capacity / Resolution 当前权威，ContentGenerate 仍是 incomplete revalidate Host。230 L0 保持单独挂起。
