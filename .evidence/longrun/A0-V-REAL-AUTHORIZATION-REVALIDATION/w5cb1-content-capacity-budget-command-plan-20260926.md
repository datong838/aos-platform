# W5CB1｜queued 内容 AgentRun→持久容量启动（施工前）

## 上位方案与现场

- 231-5 §4/§6、231-9 §2/§5 和栖月汇产品方案：内容 TaskRun 后必须由真实数字同事经当前能力、模型路由、审批、费用及容量门生成有来源的可读草稿；内部 Plan/queued AgentRun 不算产物，更不授权发布、触达或 Provider 外呼。
- W5CB0 `63cac01a` 只在 `a0v_102` accepted 后独立读回 queued AgentRun 原生 Receipt；`AipAgentRunService.transition(queued→running)` 才调容量 Gate，`ContentGenerateHostService.revalidate/execute` 才调预算 Owner 写 HELD/PENDING，正式 Provider Worker 又以提交前 Receipt 为单次外呼边界。三个边界不可合并成一句“模型已跑”。两个 Worker 默认关闭、生产迁移未应用。
- W5CB0 仍缺完整 Handoff→Plan/Run→AgentRun 的 PostgreSQL 一体化夹具；本波先补，不以分段 mock 替代。不能读取商城源、补造审批/价格/来源或手工给 Run 贴技术引用。
- 公共 `AipAgentRunService.transition` 与 `AipModelCapacityReservationGate.reserve` 各有自己的提交点，前者的容量预留甚至先于 AgentRun 状态 CAS 提交。故本波不能声称「AgentRun running＋容量＋预算命令」原子提交；容量成功／状态未知必须只读对账，不能再 claim 或换键重新预留。预算命令只能从独立读回的 running＋当前容量事实进入第二个持久阶段。

## 文件级施工与 RED

1. 扩充 `services/aos-api/tests/extension_runtime/test_ecommerce_content_agentrun_owner_pg.py`（或新完整夹具）：在一次隔离完整 schema 中以当前 Review、责任槽、发布 Skill/Logic、READY Route 与合法 Brief，证明 Handoff→Plan/Run→queued AgentRun 的同租户原生 Receipt 和失败整体回滚；错租户/旧代/Plan 漂移/多义 Slot/无来源不得创建第二 AgentRun。若当前公开 Owner 无法借事务，先修公共借用边界，不能直接 SQL 写 AgentRun。**2026-09-26 复审限时裁决**：这项完整夹具涉及此前五段独立权威的大量建模，当前分段 PG＋完整 schema 公共 Owner 回归已绿；不为测试夹具停住内容能力主线。本波如无法低风险补齐，记录为 W5CB2 前的单库接线债，不能称自然链已验收，也不能据此启生产 Worker。
2. 设计 `a0v_103`（开工核唯一 head）**容量启动意图**，在 W5CB0 AgentRun ack 原事务写 pending；独立 claim/attempt=1、UNKNOWN 冻结。ack 只接受同 TaskRun AgentRun running 且当前有效的容量 Reservation，记录容量 Ref。旧 accepted 不回填，commit 未知不重发。状态 CAS 前后均以 AgentRun＋Reservation 只读对账，不依据异常猜测回滚。
3. 新增 `services/aos-api/aos_api/ecommerce_content_capacity_owner.py`，以当前 Review/Brief/方法、W5CB0 AgentRun/Skill/Route、责任计划及安装全组为起点，经公共 `AipAgentRunService.transition`/`AipModelCapacityReservationGate` 将 queued AgentRun 转 running；之后独立读回并 ack 容量启动意图。若容量已预留但 AgentRun 尚 queued，冻结并交给正式对账，不自行再次 transition。
4. **预算命令单独一波 W5CB2**：基于 W5CB1 已确认的 running＋容量 Ref，再按 12 项 exact authority 读取 ActionApproval、Budget、ModelPriceSnapshot、事实 Evidence，确定正数费用上界与 token 界。复用增长包 `ContentCapabilityRequest` 和正式 `LockedEcommerceGrowthHostPort`，稳定命令键提交 `content.generate`，只在原生预算 HELD＋Journal PENDING 独立读回后记接受；Provider Worker 仍关闭。预算命令自身另需单次持久意图和 UNKNOWN 冻结，不能复用容量启动 claim。
5. `main.py` 新容量 Worker 默认关闭，只在同进程 ACTIVE Host、runtime-only DB 身份、当前安装/Dispatch 下可运行；专项覆盖容量耗尽、旧 epoch、并发 claim、陌生 AgentRun、状态/容量未知和 `dev-org` 零 canary。无审批、过期费用/来源、Budget/Provider 未知列入 W5CB2 预算命令专项。累计回归、完整 PG、可用时浏览器实测、方案/代码复审、verification 后才提交。

## 退出和硬边界

- 本波仅能取得容量启动**代码门**，不把 running 或容量预留叫内容完成；W5CB2 的 HELD/PENDING、真实 ProviderRequestReceipt、MeasuredUsage、Artifact、人工 Review、TaskRun 终态以及 EffectReview/Wiki 仍是后续独立门。完整单库夹具未绿时不得启真实 Worker 或声称自然链；但可以继续实现默认关闭的 W5CB2 命令代码。严禁制造容量／预算一次性伪原子。
- 原 12 Run 不重发、230 L0 挂起；不读商城源，`dev-org/dev-project` 只为零 canary。所有生产迁移、Worker 激活和 Provider 外呼仍需新鲜 scoped authority，测试绿不能授权效果。
