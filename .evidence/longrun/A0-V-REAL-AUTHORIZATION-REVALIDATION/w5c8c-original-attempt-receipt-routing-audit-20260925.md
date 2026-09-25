# W5c8c 原 attempt 双 Receipt 只读寻址审计

## 已证代码路径

1. `AnalysisSnapshotCoordinator._resume` 的 Analysis runtime 幂等键为 `snapshot-route-` + SHA256(`tenant` + 精确 `DataRequirementRevision` Ref)；`_HostAnalysisReceiptStore.read(key)` 从 `(org,project,operation,idempotency_key)` 主键读取持久响应。`_replay_committed` 虽先读该响应，但随后调用 `_resume`，因此**不能**把 `_replay_committed`/`coordinator.run` 当只读恢复器。
2. `BoundEcommerceGrowthRuntimeStore.read_exact` 可按完整目标 Receipt Ref 要求唯一并核 `request_hash/response`；`a0v_050` 的完成证据还要求 RUNNING、`completed=false`、正确 Requirement/Run 与 FulfillmentRef。只按 Requirement 查询 DataFulfillmentReceipt 可能多候选，不能凭“有一条 fulfilled”选一个。
3. `data_requirement_outbox_complete_a0v_050` 只接受当前 `claimed`、原 attempt/token、未过期 lease 与双 Receipt；`reconcile_completed_a0v_050` 只接受 `unknown`、原 attempt/token 与双 Receipt。已 `acked` 对相同原 tuple/双 Ref 可回放只作证明，W5c8b 已证明无需回放也能独立 SELECT 对账。
4. 过期 `claimed` 即使找到双 Receipt，也不能调用 `reconcile_completed`：SQL 状态不符；旧 `mark_unknown` 同样因 lease 已过期拒绝。不能通过新 claim、延长旧 lease、直接 UPDATE 或重新跑 coordinator 跨越。它需要**另立带原 attempt/Receipt/Owner 证据的审计状态迁移 authority**，并先证明 Host/Store 跨事务围栏。

## 三态只读/恢复矩阵

| 持久状态 | 可只读寻址 | 当前允许 | 必须停止的情况 |
| --- | --- | --- | --- |
| `acked` | Outbox 行已有原 attempt/token/两份 completion Ref，按精确 Ref 回读 | W5c8b 式确认，不重调 coordinator | 任一 Ref/租户/attempt/token 不同，或独立 Receipt 不一致。 |
| `unknown` | 从原 Requirement 推导唯一 `snapshot-route-*` 键，读 RUNNING AnalysisRuntimeReceipt，再以其 FulfillmentRef 独立核履行 Receipt；目前尚无封装好的纯只读 resolver | 保持冻结；设计完成并以隔离 PG 证明后，才可考虑原 tuple 的 `reconcile_completed` | 无 Receipt、多候选、PREPARING、需求/Run/来源不符、Store 结果不明。 |
| 过期 `claimed` | 可按原 Outbox/attempt/token 只读定位，尝试同上双 Receipt 寻址；W5c8a 严格 SQL 不再自动重领 | 保持冻结，不能自动转 `unknown` | lease 过期后 legacy 标记拒绝；无独立审计迁移 authority，任何新 attempt 均禁止。 |

`_HostAnalysisReceiptStore.read(key)` 只返回响应，不等于 `read_exact` 或 `a0v_050` 全部证据谓词；只读 resolver 必须做强校验且不得调用 `_resume`。运行中服务/真实 DB 尚未接入 W5c8a 的新严格代码，本矩阵不提升真实 A0-V 授权。W5c8d 应先实现**纯只读**唯一寻址及负例；状态变更另设独立方案，不把“找到候选”直接解释为可恢复。
