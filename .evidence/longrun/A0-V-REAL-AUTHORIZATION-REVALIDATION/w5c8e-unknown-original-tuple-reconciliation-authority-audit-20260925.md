# W5c8e unknown 原 tuple 对账 authority 只读审计

## 结论

当前**不能**将 W5c8d 双 Receipt 诊断结果直接传入 `reconcile_completed`，更不能自动接线。`a0v_050` 的数据库函数在一个事务里锁定 Outbox delivery 并核 `unknown`、原 attempt/token 和双 Receipt；但它不核当前 Host lease、源组保存绑定、全机拓扑或上游 Store 提交围栏。W5c8d 解析器核原 Requirement/Run/Case/Occurrence 及双 Receipt，但未读 `PipelineSnapshotGroupLocator` 的完整成员/manifest。两者证据并列，不形成端到端恢复 authority。

## 证据来源与时间点

| 证据 | 现有读/锁 | 覆盖 | 缺口 |
| --- | --- | --- | --- |
| `DataRequirementOutboxStore.read_ambiguous_next` / W5c8d resolver | 只读，原 Outbox tuple；`REPEATABLE READ READ ONLY` | `unknown`/过期 `claimed` 原 attempt，RUNNING/唯一 PREPARING、履行 Receipt | 只是一份事务快照，不能授权后续写入。 |
| `AnalysisDataRequirementRouteReader.read_unknown` | 原 Requirement、PREPARING Receipt、accepted occurrence、`PipelineSnapshotGroupLocator` | 原 Run 到完整保存源组成员/manifest、actor/cutoff | 依赖当前 requirement/head 与当前 claims 对象；不等于后续消费时的 Host/Store 新鲜 authority；不能调用 coordinator 当读取。 |
| `data_requirement_outbox_reconcile_completed_a0v_050` | `FOR UPDATE` 锁 delivery，原 tuple 与双 Receipt 原子核验 | 防错误 attempt、token、缺/错双 Receipt 与非 `unknown` 状态 | 无 Host lease guard、源组绑定/manifest 谓词；函数成功不证明上游跨事务效果围栏。 |
| `extension_runtime_host_lease_worker_fence_a0v_094` | 单事务 advisory lock、lease/identity/assignment `FOR SHARE`，token/epoch、DB 时钟 | 若真实启用并在同一写事务调用，可拒绝非当前 Host holder | 当前 Analysis Outbox 对账 SQL 未调用；W5c8d 只读诊断无 Host token/epoch；真实全机拓扑和 Fresh Owner 门仍不全。 |

## 禁止推断与停止条件

- `read_unknown` 的路径是只读 lineage，不是独立恢复命令；`AnalysisDataRequirementWorker._run_claim(reconcile=True)` 会建 coordinator 并 `run(route=...)`，存在重复源/多提交风险，绝不可当作安全对账入口。
- W5c8d 结果可证明“隔离 PG 内某一快照存在精确双 Receipt”；从只读事务结束到 `a0v_050` 写事务之间若 Host/源组/Store authority 变化，不能只靠旧证明迁移状态。
- 过期 `claimed` 既不满足 `reconcile_completed` 的 `unknown` 状态谓词，也不能被时间阈值自动转换；本波不讨论写入它。
- 真实服务尚未加载 W5c8a/d，真实 DB 未迁入 a0v_095。真实 12 原 Run running、stalled closure Receipt 0；任何真实对账或恢复都须等待独立全机 Host/Owner/plan/key 门。

## 后继最小项

W5c8f 先构造**纯只读原源组证据**：从原 Run、Requirement cutoff 和 PREPARING Receipt 定位唯一保存组，核完整成员/manifest、actor、source control/ref；与 W5c8d 双 Receipt 结果交叉核对，但仍不写 Outbox。随后另立单事务 Host-fenced `unknown` 对账设计及隔离 PG 正/负例；在真实门未闭合前不接自动 Worker。
