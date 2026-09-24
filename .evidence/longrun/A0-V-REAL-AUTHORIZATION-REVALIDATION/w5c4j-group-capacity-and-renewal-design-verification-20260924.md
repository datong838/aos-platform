# W5c4j 组负载与控制续期设计验证（2026-09-24）

方案 `209531ef`；本波只读代码、历史证据及当前配置，未读取商城源行、未改定义或执行状态。

## 当前执行链事实

- `PipelineSnapshotScheduleWorker.serve` 每轮只创建一个 `tick` 线程任务；`tick` 按定义逐个调用，`run_definition` 对本定义持有独占 advisory lock。`PipelineSnapshotScheduleRuntime.execute` 先提交 12-run group claim，再在一个 `read_selected_snapshot_group` 中读取整组；其底层 `read_snapshot_group` 只用一个私有只读事务，按 12 个 read spec 顺序执行，不存在 12 个并发源连接。
- 完成阶段 `ControlledSnapshotGroupObjectExecutor.execute` 对 12 个 member 按 ref 排序逐个 `resume_saved`，然后才执行组关系/链接/退休等阶段。当前代码并非“12 路并发 Python worker”。历史 W4 的 2 CPU/3 GiB 资源/续租饥饿真实，但旧注释的“12 同时派发”应理解为一个 slot 一次建立 12 条 Run，并不能据此要求无根据的并发重构。
- 源快照读有现成 30 秒以内控制限制，真正耗时风险在整组完成及 Store/投影/续租；`tick` 未传固定 300 秒 deadline，不能用“每天一次”证明一次必达。已有独立 attempt/失败与保存恢复路径负责 fail closed。

## 最小续期路线

`PipelineSourceSelectionDraft` / `PipelineRuntimeControlDraft` 的窗口允许最多 24 小时；Owner 的 append 支持精确 `previous_ref`，绑定可在同 schedule/binding ID 上追加 revision，disabled definition 的 `configure` 可追加 rev2 并重指 12 个最新 binding。这必须作为 **Selection rev2 → Control rev2 → Binding 下一 rev → disabled Definition rev2** 的串行子波，每一项新 key、0600 intent/result、逐波验证/提交；不可原地篡改 rev1 时间，也不可沿用过期引用。以当前时刻生成 24 小时窗口可覆盖今日 20:00 UTC slot 及后续组处理，但启用前仍要重核预算 rev13 到期、Host/三 held、worker 独立单例、在途0 与 canary0。正式授权窗口取新 12 条交集，至少覆盖预期开始和有界最长执行时长，不能只覆盖起始一分钟。

下一波 W5c4k：先只读核 Window/Host/预算与当前 rev1 权威，生成并隔离预检新的 24 小时 Selection rev2 草案，不发业务 Run；之后 l/m/n/o 分波完成链与 enable 的独立门禁。出现任何未知提交边界即冻结只读对账，不重发。
