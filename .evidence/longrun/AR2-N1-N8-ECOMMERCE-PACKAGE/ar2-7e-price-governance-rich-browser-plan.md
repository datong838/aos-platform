# AR2-7E 价格治理非空隔离功能补齐与验收方案

日期：2026-09-10

分支：`m1`

基线：`9c8aeb49`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：产品代码修改前冻结

## 1. Rules 与方案依据

- 231-6 动作表要求价格页覆盖监测规则、异常、策略草稿、对比预览、批准与执行结果；R7-P01～P05 要求三标签、筛选、内部策略版本、采集计划、预览、审批、Receipt 和三视口验收，真实抓取与真实调价保持门控。
- `16-价格治理技术方案.md` 已确认 MonitoringPolicy、PriceResearchBatch、PriceCase、Disposition 为 tenant-scoped append-only authority；调价持续 `disabled / R4-specialized-gate-required`。
- 当前页面只有三只读标签、审计展开和刷新，没有策略草稿、对比预览、审批前预览或 Receipt 工作流，无法用验收脚本绕过。
- 本切片使用通用 AIP Action Proposal 承载内部策略草稿与替代版本；价格领域 GET 继续作为观察、监测规则、PriceCase 与 Disposition 的来源。不新增任意 URL、Provider、ResearchJob、通知或调价命令。
- AR2 浏览器仅使用隔离合同 fixture；不冒充栖月汇真实数据和 A0-V/A1 验收。

## 2. 产品最小补齐

- 三标签保持 `同款价格治理 / 竞品比价 / 调度控制台`；增加 `全部 / 可比 / 待复核 / 已排除` 观察筛选、可见异常选择与可信空反馈。
- 右侧增加“内部价格策略”工作区：新建／编辑标题、容差、新鲜度和说明；提交形成 `ecommerce.price.prepare-strategy`、R2、`externalEffectAllowed=false`、`repricingAllowed=false` 的 Action Proposal。
- 修改使用 replacement proposal，不能静默覆盖旧版本；提供对比预览、timeline 回读、审批前预览与撤回。审批前预览只说明独立审批、租约和专业调价门仍未满足，不调用 decision/lease/execute。
- 增加“立即采集预检”，只展示来源许可、capacity/budget 与 Provider 未授权的 blocked 结果，网络写请求保持 0。
- 正式价格观察、贡献和处置 GET 刷新后不受内部草稿污染；保留现有 audit context、remedy、closure 与零外部效果陈述。

## 3. 文件与 preHash

- `apps/web/src/components/workshop/PriceGovernancePage.tsx`：`23a1cd953b49901471070c03473e771c664cb2e9086df84c7c71c07c8e449893`
- `apps/web/src/components/workshop/PriceGovernancePage.test.tsx`：`87fdaa1909c477ef53e9b877c2e196bd060bab343cd8dcb81c3270b1fdb60824`
- `apps/web/src/styles/45-ecommerce-workshop.css`：`3af78df1279b589863d833bac5d744cbb6500bc703140ec63a401d71ff54ed03`
- `apps/web/src/api/aipActions/client.ts`：`7bc57111c69c649c0ea36d9015fcae8881b258a661573cd12af54b92ebf6c37c`（只消费，不修改）
- 计划新增执行器、JSON、三张截图和验证文档：同证据目录 `ar2-7e-price-governance-rich-*`。

## 4. 单元与三视口固定动作

- 单元测试覆盖四筛选、可信空、草稿 create/replacement、CAS 载荷边界、对比预览、审批预览、timeline、撤回与立即采集零 transport。
- 每个 `1280×720 / 1440×900 / 1920×1080` context：切换三标签和四筛选；选择两条观察；展开六轴审计与累计审计；完成策略 `新建 → 保存 → 对比预览 → 修改 → 提交修改 → timeline → 批准预览 → 撤回`；执行采集预检；刷新四个正式 GET；折叠／恢复侧栏并滚动到底。
- AIP 写序列每视口严格为 `create draft → submit draft → create replacement draft → submit replacement draft → timeline GET → withdraw replacement proposal`；所有 POST 在 Playwright 路由截获。

## 5. 退出条件

- 三视口 `3/3 PASS`；三标签、四筛选、两观察、六轴、策略两版本、对比预览、审批前预览、timeline、撤回、采集预检、刷新和页面几何全部通过。
- 所有写请求仅为 5 个被截获的内部 Action Proposal 请求；批准、租约、执行、通知、ResearchJob、Provider、调价、退款、客户消息和外部业务 mutation 全为 0。
- Web 全量、production build、`verify_closure.py --phase ar2-7` 与 `git diff --check` 全绿。
- 本切片通过后继续客户关系页面，不前推 7E 总体标记。
