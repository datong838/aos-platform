# W5CB1｜内容 AgentRun 持久容量启动代码门（2026-09-26）

## 结论

- 完成**默认关闭的容量启动代码门**，不是业务链 GREEN。公共 AgentRun transition 先以当前 READY Route 通过容量 Gate 持久预留，再独立提交 running；本波把这两个非原子边界显式分开，不把容量当费用预算。任何异常／提交未知都保留已消耗的一次 claim，不自动重试、不换键重发。
- `a0v_103` 在 W5CB0 queued AgentRun 原生 Receipt 的 ack 同事务写下游 pending，拒绝历史 accepted 补写；claim 仅 attempt=1。ack 要求同 TaskRun 的 running AgentRun 与尚未过期的容量 Reservation，记录 Ref；服务独立读回才报告 `CONTENT_CAPACITY_RESERVED`。
- 容量 Owner 启动前核当前全组 Review/Brief/来源/方法、不可变 Plan 责任槽与已发布 Skill/READY Route、唯一原 AgentRun 快照；如已有容量预留或 AgentRun 不是 queued，不消耗下一 attempt。公共 transition 与容量 Gate 都用 runtime-only scoped 连接；Worker `AOS_ECOM_CONTENT_CAPACITY_WORKER_ENABLED` 默认关且必须同进程 ACTIVE Runtime Host。

## 验证与未验边界

- RED：新迁移/新 Owner 不存在时对应测试失败。专用 PostgreSQL 16 最小意图/RLS 夹具 **5 passed**，覆盖 ack 同事务、历史不补、单次 claim、running＋有效容量 ack、`dev-org/dev-project` 零读；容器已停并自动移除。
- 邻接累计 **59 passed，7 既有 warnings**，含 W5CAZ/W5CB0、责任槽、公共 AIP transition/容量 Gate、容量 Owner 成功/未知路径。`alembic heads`=`a0v_103`，编译和 diff check 通过。8080 无监听，本波没有适用的真实浏览器业务验收；不把单元／隔离 PG 当真实页面或真实能力结果。
- 完整 Handoff→Plan/Run→queued AgentRun＋容量 Owner 的**同一完整 PostgreSQL schema 一体化夹具未完成**。本波方案已记录限时裁决：它保持单库接线债，禁止基于本代码门启生产 Worker 或声称自然链成功；为避免夹具复杂度阻住核心业务研发，允许继续 W5CB2 默认关闭的预算命令实现。
- 生产数据库未应用 `a0v_103`，三个内容 Worker 未启用，未建立真实 AgentRun running、预算 HELD、`content.generate` Journal、ProviderRequestReceipt、用量或可读 Artifact。原 12 Run 不重发，230 L0 挂起，未读商城源。

## 方案/代码复审与下一波

- 对照 231-5 §4/§6 与 231-9 §2/§5：容量和预算各自持久 Ref，真实能力调用仍需当前 ActionApproval、Budget、价格、来源与 exact 命令；内部 running 不可替代 Provider 或内容产物。复审修复了既有权威读取带 `FOR SHARE` 却接只读事务的风险，改为 runtime-only 可加锁事务；无 Web 身份回退。
- W5CB2：先写文件级方案；从已接受的容量启动意图独立创建单次预算命令意图，读取 12 项当前 exact authority，经正式 `LockedEcommerceGrowthHostPort` 提交 `content.generate`，仅在原生预算 HELD＋Journal PENDING 独立回读后确认。补单库一体化夹具及运行身份权限，保留 Provider Worker 默认关；然后才考虑有权威的自然实例。
