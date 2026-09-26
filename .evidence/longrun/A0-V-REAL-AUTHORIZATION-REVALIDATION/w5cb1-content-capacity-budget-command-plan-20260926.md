# W5CB1｜queued 内容 AgentRun→容量／预算／持久生成命令（施工前）

## 上位方案与现场

- 231-5 §4/§6、231-9 §2/§5 和栖月汇产品方案：内容 TaskRun 后必须由真实数字同事经当前能力、模型路由、审批、费用及容量门生成有来源的可读草稿；内部 Plan/queued AgentRun 不算产物，更不授权发布、触达或 Provider 外呼。
- W5CB0 `63cac01a` 只在 `a0v_102` accepted 后独立读回 queued AgentRun 原生 Receipt；`AipAgentRunService.transition(queued→running)` 才调容量 Gate，`ContentGenerateHostService.revalidate/execute` 才调预算 Owner 写 HELD/PENDING，正式 Provider Worker 又以提交前 Receipt 为单次外呼边界。三个边界不可合并成一句“模型已跑”。两个 Worker 默认关闭、生产迁移未应用。
- W5CB0 仍缺完整 Handoff→Plan/Run→AgentRun 的 PostgreSQL 一体化夹具；本波先补，不以分段 mock 替代。不能读取商城源、补造审批/价格/来源或手工给 Run 贴技术引用。

## 文件级施工与 RED

1. 扩充 `services/aos-api/tests/extension_runtime/test_ecommerce_content_agentrun_owner_pg.py`（或新完整夹具）：在一次隔离完整 schema 中以当前 Review、责任槽、发布 Skill/Logic、READY Route 与合法 Brief，证明 Handoff→Plan/Run→queued AgentRun 的同租户原生 Receipt 和失败整体回滚；错租户/旧代/Plan 漂移/多义 Slot/无来源不得创建第二 AgentRun。若当前公开 Owner 无法借事务，先修公共借用边界，不能直接 SQL 写 AgentRun。
2. 设计 `a0v_103`（开工核唯一 head）内容执行阶段意图，在 W5CB0 AgentRun ack 原事务写 pending；独立 claim/attempt=1、UNKNOWN 冻结、ack 只接受同 TaskRun AgentRun running + 当前容量 Reservation + 同 exact 生成命令的预算 HELD/PENDING Receipt。旧 accepted 不回填，commit 未知不重发。
3. 新增 `services/aos-api/aos_api/ecommerce_content_command_owner.py`，以当前 Review/Brief/方法、W5CB0 AgentRun/Skill/Route、责任计划及安装全组为起点，先通过公共 `AipAgentRunService.transition`/`AipModelCapacityReservationGate` 把唯一 queued AgentRun 转 running 并持久容量 Ref；再按 12 项 exact authority 从当前 Owner 读取 ActionApproval、Budget、ModelPriceSnapshot、事实 Evidence，确定正数费用上界与 token 界。无一项合法则在 effect 前保留 pending，不做假 Ref。
4. 复用增长包 `content_capability_runtime.ContentCapabilityRequest` 和正式 `LockedEcommerceGrowthHostPort`，以稳定命令键提交 `content.generate`；Host 必须写原生预算 HELD + Journal PENDING，并独立读回。Provider Worker、Consumer 开关不由本波自动打开；容量预留与费用预留分别记录，任一未知进入对账而不换键重发。
5. `main.py` 新 Worker 默认关闭，只在同进程 ACTIVE Host、runtime-only DB 身份、当前安装/Dispatch/审批与预算下可运行；专项覆盖无审批、过期费用/来源、容量耗尽、旧 epoch、并发 claim、陌生 AgentRun、Budget/Provider 未知和 `dev-org` 零 canary。累计回归、完整 PG、可用时浏览器实测、方案/代码复审、verification 后才提交。

## 退出和硬边界

- 本波不把 HELD/PENDING 叫内容完成；真实 ProviderRequestReceipt、MeasuredUsage、Artifact、人工 Review、TaskRun 终态以及 EffectReview/Wiki 仍是后续独立门。若公共 Owner 不能安全跨容量/命令边界，拆成两个有持久 Receipt 的后续子阶段，明确剩余事项继续推进，不制造一次性伪原子。
- 原 12 Run 不重发、230 L0 挂起；不读商城源，`dev-org/dev-project` 只为零 canary。所有生产迁移、Worker 激活和 Provider 外呼仍需新鲜 scoped authority，测试绿不能授权效果。
