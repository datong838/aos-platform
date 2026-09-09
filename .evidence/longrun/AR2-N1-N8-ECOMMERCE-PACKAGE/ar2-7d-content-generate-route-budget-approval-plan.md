# AR2-7D Content Generate Route / Price / Budget / Approval 权威

基线 `m1@e35ba59e`。依据 231-6 D1 与已交付 7A receipt-first budget authority，在 Agent/Responsibility/Capability 输入权威之后继续闭合 ContentGenerate 的当前 ModelRoute、价格、预算与批准。这里只读复验，不创建 invocation/reservation，不调用 Provider。

## Owner 与判定

- ModelRoute 以 tenant-scoped `public.aip_model_route_head/revision` 为 Owner；共享锁定 head，要求命令 revision 为 current revision 且 head version 一致，原始 payload 通过 `ModelRouteRevision` 严格解析，并按 `AipModelRuntimeStore` 发布口径排除 meta 字段重算 content hash。排除摘要的 tenant/revision 仍须与 scope/exact ref 原值一致，关闭 Pydantic 对 `1 -> true` 等弱类型归一化。Route 必须 ACTIVE、输入/输出模态均为 TEXT，requiredCapabilities 包含当前 Capability ID。
- Price/Budget/Approval 直接复用 `AipBudgetReservationStore._price_authority/_budget_authority/_approval_authority` 的现行 7A 判定，并使用数据库 `clock_timestamp()` 作为同次 cutoff。Price 原始 payload 须按 ModelRuntime 发布口径复算摘要，并逐项核 tenant、revision、ID、contentHash 与 lifecycle；Budget 要求 active/effective/exact；Approval 要求 exact/approved/unexpired。
- Proposal 正文权威使用原 `AipActionStore` 在 `aip_action_draft.snapshot` 保存的 stable snapshot：复算 proposal hash，并对账 Proposal 行的 payload、Task、operation、action binding、createdBy 与 expiry；命令 upperBoundFen 必须与经稳定摘要保护的 payload 精确相等。
- 上述 7A 只读查询默认显式限定 `public.`，防止 Host/TEMP search_path 影子表；`AipBudgetReservationStore(authority_schema=...)` 仅供隔离测试注入经白名单验证的 schema，生产默认仍为 public，业务条件不另造第二套。

## 修改与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：增加 route/budget/approval revalidate 并接到现有 ContentGenerate 输入链。
- 修改 `services/aos-api/aos_api/aip_budget_reservation_store.py`：对 Budget/Price/Task/Approval/Proposal Owner 查询补 schema 限定，并补 Price 原文与 ActionStore stable Proposal snapshot 的 canonical 读取；为后续 reserve 保留同一判定。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_route_budget_approval_authority.py`，覆盖 current/hash/lifecycle/modality/capability、Route tenant/revision 原值、Price 原文、Proposal snapshot/upper bound、cutoff/effective/approved/proposal binding、tenant/TEMP 与弱类型关闭；回归 7A budget、ModelRuntime、ContentGenerate/Review 邻接。

## 边界与下一步

本段不解析 Secret、不选择或调用 Provider、不创建 CapabilityInvocation/BudgetReservation/Artifact，不改变 bucket，不产生费用或外部副作用，不实现 execute/verify、不加入 readiness seal。Price 与 Route 具体候选 Model 的关联尚由下一 Capacity/Resolution 切片证明；CapacityReservation 不能只按 ID 接受，下一段必须对账其 pool、route/model/provider exact tuple、agent run 与有效状态。230 L0 保持挂起。
