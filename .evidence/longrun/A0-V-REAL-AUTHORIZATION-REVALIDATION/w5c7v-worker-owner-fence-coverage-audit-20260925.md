# W5c7v Worker/Owner 启动与事务 fence 覆盖矩阵（只读）

下表只陈述已审代码路径，不把局部 `host_ready()`、当前数据库登录或既有安装/dispatch gate 等同 Host lease。W5c7u 新参数仍 default off；真实库没有 `a0v_093/094`。

| 启动/写路径 | 当前入口与提交边界 | Host lease/fence 读回 | 路由 |
| --- | --- | --- | --- |
| API 独立/共宿 Snapshot worker | `main.py::_start_snapshot_group_worker` → `PipelineControlServiceFactory.build_snapshot_worker(scope, store)`；独立模式不启动 Runtime Host，`host_ready` 仅进程存活 | 工厂可显式透传 lease，但 `main.py` 未传；真实 worker 无 lease | 保持 default off；独立启动的 acquisition/renew/stop 与真实迁移另起方案；不能凭 API 状态证明全机。 |
| A0-V Runtime Host | `scripts/a0v_ecommerce_runtime_host.py::_serve` 构建 Host/三业务 worker，后按 flag 可选 acquire/renew；launchd 未带 flag | lease 只由脚本持有，没有向三业务 worker/ControlFactory 注入；`host_ready()` 只是任务活性 | 不得启用 flag 后即宣称 worker fenced；须逐调用链同事务 guard。 |
| Product event worker | `ecommerce_product_event_worker.py` 中 `_discover`/`_markings` 只读；`AutomationOccurrenceStore` claim/dispatch receipt 与 `build_event_consumer/analysis` 可能写，`_authoritative_store` 另有提交边界 | 工厂/worker 无 `host_lease`；Automation Store 独立连接/commit 无 Host lease | 需单独设计 claim、Receipt 与事件效果的身份/未知边界；不以消费前 `host_ready` 代替。 |
| Analysis DataRequirement worker | `ecommerce_analysis_data_requirement_worker.py` 的 Outbox `claim_next`、fail/unknown/complete 均由 `DataRequirementOutboxStore` 自有连接/commit；coordinator/Store 另事务 | Worker/Outbox 无 Host lease；既有 delivery lease 不是 Runtime Host lease | 严格区分 outbox delivery token 与 Host epoch；跨事务失败冻结，不自动重发。 |
| Baseline assessment worker | `ecommerce_baseline_assessment_worker.py` 的 once-slot、Occurrence claim、target Receipt/needs-attention 与 `_authoritative_store` 多提交边界 | Worker/Occurrence Store 无 Host lease | 需逐事务 guard、过期 claim 和 target Receipt 对账；自然触发不得作为旧 attempt 续发依据。 |
| PipelineControlServices Owner | `pipeline_control_service.py::_approve`、`bind_schedule` 通过 `consumer_connection` 单独事务写 source selection/control/binding | 当前无可选 Host lease；W5c7u 只改 Snapshot worker 构造 | 可作为下一波 W5c7w 单一、可隔离的默认 off 同事务 fence 候选；先确认当前 Owner 锁/RLS 和事务上下文，不直接扩大到生产。 |
| Schedule original/recovery 内部 | `PipelineSnapshotScheduleRuntime` 与 `PipelineSnapshotGroupRecoveryRuntime` 以及下游 Completion/Ingress 已有 opt-in 参数和部分同事务 guard | 仅在显式传 exact 已 acquire lease 时成立；API 生产未注入，Store 独立效果另审 | 局部代码证明不等于全路径/全机证明，保持真实禁入。 |

结论：存在实质未覆盖路径，不能把 W5c7u 工厂接口外推为“全 worker fenced”。本波不修改生产代码，因为 Product/Baseline/Outbox 的跨事务/外部效果需要独立身份与 unknown 合同，盲目传一对象会造假安全结论。下一波先对 `PipelineControlServices` 三个 Owner 写方法做隔离方案/测试；三业务 worker 按上表拆成独立后续波。全机控制面、真实迁移、旧 Host 停机撤权、物理第二 Host=0 和 Fresh Owner closure 仍是分立门。
