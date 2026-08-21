# R12 电商六角色 37 Logic 运行就绪唯一矩阵 EvidencePack

结论：`GREEN_WITH_WARNINGS`。R12 自身的 37 Logic 发布、绑定、TTL 诚实性、六角色运行就绪、负向租户隔离和五页面浏览器验收均为 GREEN；警告来自 R12 范围之外的跨页面能力/工具/路由投影、已有 Web 类型检查问题，以及尚未解除的 Workshop 外部依赖。

## 权威截止点

- 正向租户：`org-org/dev-project`；页面回读：`栖月汇商贸有限公司 / 默认工作区`。
- 最终只读矩阵截止点：`2026-08-21T10:38:22.219799Z`。
- 新鲜度来源：Agnes text 3/3 Health `health-agnes-text-qyh-r2-20260821102341222496`，观测时间 `2026-08-21T10:23:41.222496Z`，有效至 `2026-08-21T10:38:41.222496Z`。
- 该结论只对上述截止点成立；TTL 到期后页面与 API 必须重新显示 stale/blocked，禁止外推为持续可派发。

## 唯一数量口径

- SolutionPack canonical Logic：`37`，角色分布为活动策划师 6、内容官 8、客服专员 6、数据参谋 6、私域管家 5、导购顾问 6。
- latest published canonical Skill：`37/37`；专项 Pilot Skill：`2`（I01/V01），不计入 37 分母。
- Skill revision row：`80`；租户 SkillBinding row：`41`；其中 canonical exact fresh SkillBinding：`37/37`。
- 租户 CapabilityBinding row：`48`；canonical Capability 类：`7`，逐角色按唯一 ID 全量对账，不按历史 row 累加。
- 六个 AgentInstance：`6/6 runnable`；任一 Skill/Capability 缺失、revision 漂移、非 active、非 available 或 TTL 过期均 fail-closed。

## 代码与交互修复

- 新增默认只读的 R12 37 Logic readiness 矩阵和有界 readiness 刷新器。
- 后端 runtime 从“任一 Skill + 任一 Capability”收紧为全部 canonical Skill/Capability exact fresh 全量门。
- Registry 页面按 canonical exact ID 去重；专项 Skill、历史/provisioning/revoked Binding 不再污染角色覆盖率。
- “预检（可派发）”改为可操作的只读本地权威摘要，明确没有 Provider、AgentRun 或生产 Action 副作用。
- 暗色主题阶梯回归 AOS 既有 token，消除高亮白块和低对比文本。

## 验证

- R12 后端 targeted：`7 passed`；前端 targeted：`15 passed`。
- R06～R12 累计后端回归：`281 passed, 7 warnings`。
- `git diff --check`：GREEN。
- 工作区 Web typecheck 的唯一失败为既存的 `apps/web/src/api/aipWorkbench/parser.ts:189` 对 `AssistEvent[]` 使用 `.at`；不属于 R12 修改范围，未用越界改动掩盖。
- 内置浏览器验收：Registry、Agents、Studio、Tools、Marketplace 共 5 页；真实租户和工作区正确，console error=0，仅有 React Router future-flag warning。
- Registry 显示六角色 6/6 runnable，逐角色 exact Skill/Capability 为 6/3、8/7、6/4、6/3、5/4、6/3；预检有可见反馈。
- 负向 canary `dev-org/dev-project`：AgentInstance、SkillBinding、CapabilityBinding 均为 0，响应不包含正向租户事实。

## 安全边界

- readiness 刷新只消费已审批的新鲜 3/3 Health；Provider Health probe=3。
- 业务 Provider call=0、AgentRun=0、外部 Action=0、生产 Action=0、Secret payload read=0。
- 未重放 D03/P01/G02/S04/A02/C02 旧 Pilot，未执行 migration，未修改 Workshop、m1、authority、01/06 或共享记忆权威。

## Workshop 外部阻断

- `B5_RECEIPT_NOT_CAS_CONSUMED`：归 m1 串行 CAS；B5 `603d95c` 尚未进入已报告的 m1 `5b71a32`。
- `W2_00_SOURCE_READINESS_OWNER_MISSING`：归 Data/Adapter 唯一 owner；w1-aip 不代建第二真源。
- `W2_00_SAME_CUTOFF_EVIDENCEPACK_MISSING`：归 Data/Adapter；P01～P12 分散成功不能冒充同版本、同 cutoff EvidencePack。
- 上述三项阻断 W2-00B，但不否定 R12 AIP 范围的 GREEN。
