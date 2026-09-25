# W5c7l Parent Binding 查询与事务等价性审计（只读）

## 当前调用链与不可弱化点

`PipelineSnapshotGroupInputOwner._run` 在同一 caller transaction 中 callback 前 `_load`、同步 `execute(current)`、callback 后再次 `_load`，比较完整 `CurrentSnapshotGroupInput`；这不是无效重复，callback 期间可能有 DB/控制权变化。`_load` 每次先 `GroupClaim.read_current`（或 completed 模式）、读取原始 `pipeline_snapshot_group_input`，再对每个（最多 12）成员验证 leaf/claim、调用 `_bound_parent`，最后核 envelope hash、rows hash/数量/类型。长测的 172 次 Retirement `_load` 对应最多 2064 次本模块 member 遍历，且跨多次业务操作；不能跨 `_load` 缓存 parent 或 current。

每次 `_bound_parent`：

1. `IngressJournal.read` 用 `(org_id,project_id,run_id)` 读取已存 envelope，并重算/比对 digest 与列绑定；索引来自该表的 key，不可只取 JSON 略过 drift 检查。
2. `ControlledIngressJournal.verify_running_schedule` 再调用 `PipelineSourceClaimOwner.read_current` 或 `read_completed_current`；它在同事务下以当前控制 Owner、安装/配置/运行守卫、全局锁顺序与原 claim 的 actor/ref/预算/代际等精确条件重验。completed 分支不能降格为 running，也不能重新授权 source call。
3. `IngressJournal.verify_schedule_binding` 对 Run、Schedule、Graph、Source 逐项 `FOR SHARE`：Run 必须精确 running 或 completed；Schedule enabled/ingest/pipeline 一致；Graph payload digest/revision/source 节点一致；Source 类型/状态/config revision 一致。completed 分支还要求 executor stopped、完成时间、derived/dataset receipt 与 build/completion 零 pending。`meta_schedule_run` 有 `(org_id,project_id,id)` unique，claim 有 `(org_id,project_id,run_id)` primary key；单纯给这些 key 再加同型索引缺乏依据。

## 可研究但尚未授权的等价切片

在同一个 `_load` 的 `GroupClaim.read_current` 已对每成员完成当前 claim/control 检查后，`_bound_parent` 紧接着再次做该检查。可能的最小切片是**仅在同一事务、同一 `_load`、同一 member/ref/actor/current revision，且无用户 callback 夹在两次检查之间**，显式传递已读 claim 证明，仍读取原 envelope 并逐成员执行 Run/Schedule/Graph/Source `FOR SHARE` 和所有 hash/row 校验。必须先验证 Owner 锁、内部保存/重入、完成态与 recovery 分支在这段间隔内不会改变可见授权；否则拒绝。跨 `_load`、跨 callback、跨事务缓存一律禁止。

另一候选是把 12 个只读 envelope/Run/Schedule/Graph/Source SQL 合成同事务 batch，但 RLS、`FOR SHARE` 锁序、缺行/漂移错误码、每成员逐项校验和 PostgreSQL 当前快照/时间语义都必须保持；不能用一次 SELECT 的结果替代第二次 callback 后验证。当前没有逐子段测量，无法断定 batch 真能缩短主要耗时。W5c7m 应先做 test-only 透明探针与负例。

本审计未改代码/DB/索引，也未确认上述切片安全。W5c7k 正式长测仍 timeout124、无 GREEN；真实 A0-V 12 原 Run running、closure no-authority，商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
