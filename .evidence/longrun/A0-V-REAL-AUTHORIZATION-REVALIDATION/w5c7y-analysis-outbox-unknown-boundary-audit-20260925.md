# W5c7y Analysis DataRequirement Outbox unknown/Receipt 边界审计

## 已审序列（不是一个原子事务）

1. `run_scope_once` 先 `read_unknown_next`；若有 unknown 则选固定旧 claim，不领取新 delivery。否则 `data_requirement_outbox_claim_biw2_004` 在 Outbox 自有连接提交；SQL 仅领取 pending 或 lease 已过期的 claimed，不领取 unknown/acked/failed。
2. `_run_claim` 回读 route/安装与 markings，再构造 coordinator。`AnalysisSnapshotCoordinator.run` 先在自己的连接验证当前策略并 commit，再调用 original `completion.complete`（可能跨元数据/Store 边界），随后又在独立连接重验 route/策略、协调并 commit；没有与 Outbox claim/ack 共事务。
3. 正常返回必须给出 exact `DataFulfillmentReceipt` 与 `AnalysisRuntimeReceipt` 双引用；Outbox `complete_a0v_050` 在自有事务核当前 claim attempt/token/lease、双 Receipt 证据，才置 `acked`；同 tuple/双引用的已 ack 重放返回 replayed。
4. 协调或 complete 返回不明时，worker 尝试 `mark_unknown`，其 SQL 只允许同 token 的当前 claimed（或原 token 已 unknown 重放），写入独立提交。标记失败被捕获并只记日志；worker 仍返回 `unknown`。此时持久态可能仍 claimed，过期后 `claim_next` 可再领。不能仅凭 Python 返回值认定 DB 已 unknown。
5. 已持久 unknown 在后续 tick 优先通过原 route/coordinator 获取 exact 双 Receipt，再由 `reconcile_completed_a0v_050` 对原 attempt/token及双 Receipt 作证据核验；失败不会在 reconcile 分支再次写 unknown，也不会直接从 unknown 回到 pending。但 coordinator 本身会运行组合逻辑，是否零新外部 source call 必须按原 saved-input/Completion/Receipt 证据单独证明。

## 必须区分的未知结果

| 现场 | 当前代码/SQL 可见行为 | 仍需证明 |
| --- | --- | --- |
| 协调结果 unknown，`mark_unknown` 确认提交 | unknown 不被 `claim_next` 新领；先原 attempt reconcile | coordinator 再入时是否只用原持久输入、零新 source call；Host lease/fence 如何跨多个事务。 |
| `mark_unknown` 自身提交边界未知或失败 | worker 返回 unknown，但 DB 可能仍 claimed；lease 过期后可再次领取且 attempt 增加 | 在重新 claim 前是否必须独立只读对账/冻结；禁止将同一不明协调操作当新源读取。 |
| `complete` 已 ack 但响应 unknown | `mark_unknown` 对 acked 会拒绝，worker 返回 unknown；下一 tick 读不到 unknown 也不能重新 claim acked | 通过独立 Receipt 回读确认终态，不能根据返回异常重发。 |

W5c7v 已确认此 worker/Outbox/coordinator/Store 没有 Runtime Host epoch 的端到端同事务 guard；delivery lease token 是另一权威，不可充当 Host lease。W5c7z 应优先隔离 PG 复现第二行的 unknown 标记失败与过期重新 claim 资格，并与真实源调用边界隔离；修复前不得给生产 worker 注入 Host lease 或触碰旧 A0-V attempt。
