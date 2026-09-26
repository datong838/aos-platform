# W5CB0｜内容 AgentRun 一次性自然接线验证（2026-09-26）

## 结论和未完成项

- 对应方案 `w5cb0-content-agentrun-capacity-command-plan-20260926.md`（`49e61346`，施工修订 `3a81a56d`、`3665374c`、`c2120b2d`）。本波达到**queued AgentRun 代码门**：W5CAZ 在 spend attempt 前核唯一当前 frozen/READY/COMPLETE `content.generate` 责任槽及 Agent/能力；内部 Plan 的生成步骤持久绑定该槽、AgentInstance、全部 exact 能力和责任计划引用。Run ack 与 `a0v_102` 下一阶段 pending 意图在同一事务提交，失败整体回滚。
- 新 Owner 只选当前 Review/Dispatch/Runtime + accepted/running TaskRun 的待处理意图，先独立 claim 唯一 attempt；再次验证原 Review/Brief/来源、获批方法的新鲜度、不可变 Plan 与当前责任槽一致、唯一同范围已发布 Skill、READY Route/Policy。然后借公共 `AipAgentRunService._create_in_transaction` 写唯一 queued AgentRun 与原生 Receipt，同事务 ack，提交后独立读回。没有 `transition(running)`、容量预留、预算 held、`content.generate` 命令、Provider 调用、Artifact 或人工评审。
- 同 Run 已有 AgentRun、额外 Skill 能力、旧/多义责任槽、Plan/来源/模型漂移均拒绝；提交或读回不明保持 claimed，不自动二次执行。新 Worker `AOS_ECOM_CONTENT_AGENTRUN_WORKER_ENABLED` 默认关，要求同进程 ACTIVE Runtime Host 与 runtime-only 数据库身份，绝不退回 Web 身份。

## 验证证据

- RED：新 Owner 不存在时收集测试失败；随后专项与邻接累计 **83 passed**（7 个既有 warnings）；最终 Owner/前段 Owner 专项 **17 passed**。
- 专用隔离 PG：`a0v_101` + `a0v_102` **6 passed**，覆盖 ack→put 同事务、claim 单次、后补旧 accepted 拒绝、无公共 AgentRun Receipt 不可 ack、旧 epoch 拒绝、`dev-org/dev-project` 零读。`pg_current_xact_id` 与旧行 `xmin` 比对由 PostgreSQL 16 实测。测试容器 `aos-w5cb0-regression-pg` 已停止。
- 完整迁移夹具：当前责任槽解析 **1 passed**，公共 Plan 带 assignee/capability 且外层回滚 **1 passed**；公共 AIP AgentRun 借用事务/原生 Receipt 的既有集成回归 **1 passed**。`alembic heads`=`a0v_102`，编译、diff check 通过。
- 8080 无监听；18181 是旧 HTTP-only 诊断。生产迁移、Worker、真实 scoped Agent/Skill/Route/预算/审批及自然业务结果均未验证；不能以隔离 PG 或 mock 证明真实首链。

## 方案一致性与后续门

- 符合 231-5 §1/§4 的内部 TaskRun→AgentRun 续接及 231-9 §2 的数字同事实际任务；GrowthPlan 评审只允许派生内部任务，不视作 Provider/发布授权。公共 AgentRun create 与容量预留/预算 held/Provider submit 是不同的正式可恢复边界，本波不把 queued 冒充能力成功。原 12 Run 不重发、不读商城源；230 L0 挂起；`dev-org` 仅零 canary。
- 未覆盖“真实 Handoff→Plan/Run→AgentRun”完整 PostgreSQL 端到端夹具；当前结果由分段权威夹具与组装测试支持，不可扩大为真实部署证明。W5CB1 先补此完整夹具，再接已 queued AgentRun 的唯一 `transition(running)`/容量 Reservation，及当前审批、预算、价格和事实来源下的 `content.generate` 持久命令。容量和费用各自 Receipt/readback；未知 Provider 边界保持冻结。W5CB1 必须先写独立文件级方案并走同一波次闭环。
