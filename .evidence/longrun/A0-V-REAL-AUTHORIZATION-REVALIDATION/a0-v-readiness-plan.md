# A0-V 真实运行授权与准入复验实施方案

日期：2026-09-10

施工分支：`aos-platform/m1`

基线：`a158f14c`

authority：`AOS-000573`

目标阶段：`A0_V_REAL_AUTHORIZATION_REVALIDATION`

## 1. 目标与完成口径

A0-V 不重新实现 AR2，也不执行 A1 真实模型任务；它按 231 总控的 A0-06，复核 A0-02／04／05 中与首链有关的安装、租户/角色权限、SourceReadiness、模型/工具健康、预算和配置是否当前有效，并验证缺凭据、拒绝权限、预算不足、过期健康、停用开关和负向租户均能失败关闭。

完成时必须形成一份当前快照，把 `verified`、`blocked`、`unverified` 分开。只有所有 A1 必需项都具备当前真实证据，且需要付费/数据出境的精确批准已经存在，才可写 `A0_V_REAL_AUTHORIZATION_REVALIDATION_GREEN`；否则以 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS` 留证并继续修复无副作用技术缺陷，不冒充首链准入。

## 2. 权威与授权边界

- 正向租户固定 `org-org/dev-project`，显示实体应为栖月汇；`dev-org/dev-project` 仅用于隔离反证。
- 当前用户授权覆盖本地开发、只读诊断、服务恢复、隔离验证和最小修复。真实 Provider 调用、费用、数据出境、外部发布/发送、调价、退款、发货和生产/共享迁移仍须精确动作与额度批准。
- 不读取、复制或记录 Secret 正文；只核对 secretRef/credentialRef 是否存在、租户是否匹配、状态与有效期是否合格。
- Prime 只作开发期只读审查，不是 AOS Provider、租户记忆或产品运行依赖。
- `230 L0` 保持挂起；不 push。

## 3. 当前启动基线

- `http://127.0.0.1:8434` Web 可访问。
- `http://127.0.0.1:18181` AOS API 在系统重启后未监听；先按仓库既有启动方式恢复，再读取 health，不能用连接拒绝代替准入结论。
- 隔离 PostgreSQL 容器 `aos-ar2-validation-20260909` 正在运行并映射本机 18434 端口。
- AR1-c PostgreSQL 容器 `aos-ar1c-pg` 正在运行并映射本机 18432 端口；A0-V 不默认将它当作当前业务数据库。

上面两条容器信息必须由执行器重新采集为机器证据；本方案不把进程存在等同于数据或能力就绪。

## 4. 只读复验矩阵

1. **服务与身份**：API health；`org-org/dev-project` principal；显示组织/工作区；负向租户不能读取正向资源。
2. **包安装与运行绑定**：读取 bundle installation、runtime installation、九个 operation binding、generation/epoch/fence、自然 slot；不执行安装/启用/卸载写操作。
3. **SourceReadiness**：读取 canonical `/v1/data/source-readiness` 与 Workshop facade；核对 tenant、cutoff、receipt、12 个来源项、freshness、quality、reconciliation 和阻断原因。
4. **数字同事与权限**：读取 Agent registry runtime readiness、六个既有 AgentInstance、职责/能力绑定和实际 principal permission；目录存在不等于可运行。
5. **模型与工具能力**：读取 model runtime overview/chain/cost、route resolution、provider health、capacity、price snapshot、Eval gate；健康过期或依赖缺失必须 blocked。
6. **预算与批准**：只读当前 BudgetRevision、任务/日/试点额度、币种、有效期、并发/最大尝试、动作 Approval 与数据用途批准；缺值不能按零或无限额填充。
7. **生产合同与首链配置**：读取 SchedulePolicy、Business Entity/Channel、ProductionContract、ResponsibilityPlan、StageTemplate、内容任务目标和反馈配置；exact ref/tenant/digest/generation 必须一致。
8. **A0-06 负向门**：在不产生业务副作用的请求上验证缺 token、错误 tenant、查询参数越权、健康过期、预算/批准缺失、disabled/fence 等拒绝可解释；不发送真实业务命令。

## 5. 实施顺序

1. 新增只读采集器与机器结果 Schema；所有 HTTP 方法限 GET/HEAD，health 除外仍为 GET。
2. 恢复本地 API，并证明加载的是当前 `m1`；读取当前登录会话或既有开发 principal，不索取/输出密码与 token。
3. 先采集正向租户，再采集负向隔离反证；同一 URL/字段口径逐项比较。
4. 对每个准入项记录 owner、当前值、证据时间、到期时间、状态、阻断码、恢复入口和是否需要额外批准。
5. 若暴露产品缺陷，先补充最小修复方案文档并提交，再编码、定向测试和复采；配置/授权缺口不得用 fixture 或改库绕过。
6. 通过确定性检查器、浏览器回读、Prime 增量只读复核、Delivery Receipt 和 authority CAS 后进入 A1；未全绿则保留 A0-V 阶段继续处理。

## 6. 停止规则

- 任一请求将触发 Provider、费用、外部副作用、生产迁移或未经批准的业务写入时停止该动作，只记录所需批准。
- token/Secret 可能进入输出时立即停止并清理临时输出。
- 同一阶段连续两次出现无法解释的真实状态漂移时停止外部读取，先核对服务版本、租户、数据库和时间基线。
- 读取结果 unknown、stale、partial 或 blocked 时如实保留，不自动重试业务动作，不伪造零值或 READY。
