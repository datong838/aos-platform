# W5CAZ｜Review Receipt 驱动内容 Plan/Run Owner 验证（2026-09-26）

## 结果与范围

- 对应已提交方案 `w5caz-review-receipt-content-plan-run-owner-plan-20260926.md`（`aa5577ee`，未知边界补充 `2ae6b1e1`）。本波完成**代码门**：Review 接受 v2 方法时，原 Handoff 事务写入唯一 `pending/attempt=0` 启动意图；自然消费者先独立持久 claim 到 `attempt=1`，再经同一串行化事务调用公共 AIP Owner 创建、批准内部 Plan、创建并启动 Run、ack 意图，提交后独立连接读回。Run 只到 `running`，未执行内容能力、未生成 Artifact、未终结 Step/Run。
- `a0v_101` 是新迁移，不改旧迁移；SECURITY DEFINER 限定当前租户、原 Review/Dispatch/Runtime、同 Task 已批准 Plan、同 Task running Run、稳定幂等键与 Review Receipt 绑定。运行角色不能直接 DML 意图。开关 `AOS_ECOM_CONTENT_TASKRUN_WORKER_ENABLED` 默认关闭，只在同进程 ACTIVE Runtime Host 与 runtime-only DB 身份下启动。
- Review 原回执仍准确声明 `taskRunCreatedCount=0`；启动属于后续独立可审计阶段。已有旧 Review 回执不回填、不重放。claim 后任一错误或独立读回不明均留下已花费的 attempt，禁止自动重发；必须只读对账/正式 successor。

## 文件与验证

- 新增 `services/aos-api/alembic/versions/a0v_101_ecommerce_content_taskrun_intent.py`、`services/aos-api/aos_api/ecommerce_content_taskrun_owner.py`、两份同名 Owner 单元/PG 测试；最小修改 `ecommerce_growth_runtime_adapters.py`、`main.py`、Handoff 单元与 TaskBrief PG 测试。
- RED→GREEN：v2 Handoff 同事务 intent 单测；claim/ack、错 Run 键、租户零 canary、旧 epoch、运行角色拒绝直写的专用 PostgreSQL 测试 **3 passed**；完整迁移夹具 Task/Brief/AIP 事务回滚测试 **3 passed**；邻接累计 **72 passed**；最终 Owner 专项 **6 passed**。`alembic heads`=`a0v_101`，编译、`git diff --check` 均通过。测试中发现 Alembic 对 SQL 字面冒号作绑定解析，已改成 `chr(58)` 并重跑为绿。专用测试容器 `aos-w5caz-regression-pg` 已停止。
- 8080 无监听；18181 仅旧 HTTP-only 诊断实例。Worker 未在真实安装启用，无真实自然 Run、浏览器活体验收或 Provider 效果；这部分仍是独立门，不能由单元/隔离 PG 推定完成。

## 方案一致性、风险与后续

- 与 231-5 §1/§4、231-9 §2 的“exact 评审→内部内容任务”一致；本波不将 GrowthPlan 评审解释为 Provider/发布授权，内部 Plan 风险字段显式禁止外部发布与 Provider 调用。执行前再核当前完整 cutover group、原 Review 精确回执、Task/Brief 和批准方法/来源；任一过期即 fail closed。
- 当前没有完整真实安装下的自然 Review→Run 一体化验收；运行角色能通过 DB 函数花费 claim，但无额外 effect 权限，当前生产开关关闭。已 claim 后故障的恢复只可只读对账和新 successor，不得在原 intent 内二次执行。原 12 Run 不重放；不读商城源；230 L0 继续挂起；`dev-org/dev-project` 仅零 canary。
- 下一波 W5CB0：先计划 AgentRun/容量与 `content.generate` 自然命令的最小接线，保持 Provider、外部发布、人工审批和结果终态的独立门；仍不启用真实 Worker。按“上位方案→文件级计划→实现→专项/累计→活体验收能力界限→复审→证据/记忆→下一波”执行。
