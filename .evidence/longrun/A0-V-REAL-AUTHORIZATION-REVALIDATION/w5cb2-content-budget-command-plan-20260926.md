# W5CB2｜内容容量后 exact 预算命令入队（施工前）

## 上位方案与现场

- 231-5 §1/§4/§6、231-9 §2/§5、栖月汇产品方案及 W5CB1 verification：首链此段要让真实数字同事在审批、能力、容量、预算、价格和来源约束下生成有来源草稿。W5CB1 `2f4be2c7` 只给默认关闭的容量启动代码门；生产 `a0v_103` 未应用，Worker 未启，完整 Handoff→容量同库夹具仍待验。预算 HELD/Journal PENDING、ProviderRequestReceipt、Artifact 均为独立阶段，不可冒称能力完成。
- 当前正式 `ContentGenerateHostService.revalidate/execute` 已检查 12 项 exact authority、四类分析 Artifact、factSourceRefs、正数费用与 token 上界，并通过 `LockedEcommerceGrowthHostPort.commit` 在受锁事务中写预算 HELD＋内容 Journal PENDING。W5CB2 的职责是**从当前 Owner 事实构造合法命令并持久单次交接**，不复制预算/审批/来源判定逻辑，也不发 Provider。
- 旧 12 Run、230 L0 与商城源读继续保持原边界；`dev-org/dev-project` 只作零 canary。用户优先要求推进可读业务产物主线；历史逐行补证和复杂夹具不得无限吞噬本波，但生产激活仍必须补齐权威与同库验收。

## 文件级施工与 RED

1. 查 `alembic heads` 后写 `a0v_104` 单次内容预算命令意图：在 W5CB1 容量 ack 原事务建 pending，锁定 reviewKey、TaskRun、AgentRun、容量 Ref 和当前安装代次；旧 accepted 不回填。独立 claim attempt=1；任何不确定状态留 claimed/UNKNOWN，绝不换键重发。ack 必须读到同 exact 命令键的预算 HELD、Journal PENDING 及原生 Runtime Receipt，且仅引用原容量 Ref。
2. 新增 `services/aos-api/aos_api/ecommerce_content_budget_command_owner.py`：从当前 Review/Brief、Plan/AgentRun、容量意图、安装全组重验；解析当前 BudgetRevision、ModelPriceSnapshotRevision、ActionApprovalEvent、事实 EvidenceBundle，计算可执行正数费用上界与 input/output token 上界。任一权威缺失、过期、跨租户、多义或请求内容不一致，则在 claim 前 pending/禁入；不可让工程师或前端补造 Ref。
3. 复用正式 `ContentCapabilityRequest`／增长 `ContentGenerateHostService` 和 `LockedEcommerceGrowthHostPort.commit` 提交稳定 `content.generate` 命令。Host 自己执行 12 项 current revalidate 和预算 reserve/Journal enqueue；Owner 只在提交后独立读回 HELD＋PENDING＋Receipt 才 ack。预算 unknown、Host commit unknown、Provider 提交未知均冻结，不做第二次调用。
4. `main.py` 新 Worker 默认关闭，需同进程 ACTIVE Runtime Host、runtime-only DSN、当前 Dispatch/安装；Provider Worker 维持关闭。专项与隔离 PG 覆盖无审批、费用/价格/来源过期、旧 epoch、容量到期、并发 claim、同键重入、预算不足、跨租户与 `dev-org` 零 canary；先 RED 再最小实现。
5. 累计回归、完整 schema 下公共 Host/预算/Journal 合同回归、可用时浏览器验收、方案/代码一致性复审、verification 落盘、m1 精确提交、D-waves/AOS/Prime 上下文更新。W5CB1 留下的一体化 Handoff→容量夹具作为生产激活前硬门，若本波仍无法安全补齐，继续如实列待验而不阻止下一段默认关闭的核心业务代码。

## 退出/停止条件与下一波

- 本波最多声称 `content.generate` PENDING/HELD **代码门**，不声称模型已调用或文案已生成。下一波 W5CB3 接正式 Provider 单次提交/结果消费/MeasuredUsage/可读 Artifact，随后人工评审、TaskRun 终态与反馈续跑各自验收。
- 只有当前 scoped authority 和新鲜读回可推进真实实例；任何未知提交不重发、不手工 run_definition。生产迁移/Worker 激活另需安装权限、审批/预算/来源及完整单库夹具，不能靠测试绿替代。
