# P5D 可观测性业务化验证

- 日期：2026-08-31
- 范围：`ObservabilityPage`、页面单元测试、AIP Evidence SDK 回归。
- 业务入口：最近真实任务运行、最近受控动作；原始 `lineageId` 仅保留在高级定位区。
- 权威边界：页面仅消费服务端返回的 exact `lineageId`、Telemetry Span 与 Usage Receipt；空记录显示“缺证”，不解释为业务数量 0。
- 业务语义：步骤、错误、重试、队列、Token、成本、预算约束、告警处置、质量与问题均以中文主阅读层展示；trace/span/receipt 标识收纳于审计详情。
- 深链：保留谱系反向跳转，并提供容量预算、风险告警、评测问题入口。
- 专项测试：`ObservabilityPage.test.ts` 8/8 GREEN。
- 累计回归：`aipEvidence/client.test.ts` 11/11 GREEN；合计 19/19 GREEN。
- 类型检查：`pnpm --filter @aos/web exec tsc --noEmit` GREEN。
- 浏览器验收：不在本子项伪造；归入 P5F，启动真实 Web/API 后逐页检查布局、滚动、交互和真实租户空/有数态。
- 外部副作用：0；真实业务数据写入：0。
