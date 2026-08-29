# Workshop 八个一级菜单蓝图与功能复验

## 验收输入

- 当前页面：`http://127.0.0.1:5173/workshop/*`
- 正式视觉源：`http://127.0.0.1:8765/palantier/foundry/html/workshop-*.html`
- 浏览器：Codex 内置浏览器
- 实测视口：`1280×720`
- 真实租户：`org-org/dev-project`
- 原则：视觉源中的演示人物、任务和经营数字只用于布局比较，不复制到当前业务页面。

## source/current 新鲜截图矩阵

| 一级菜单 | 正式视觉源截图 | 当前页面截图 | 结构与功能结论 |
|---|---|---|---|
| 日常任务总控大屏 | `reference-1280x720/cockpit-1280x720.png` | `current-1280x720/cockpit-1280x720.png` | 壳层、指标条、命令条、执行组/任务流/策划组、复盘栏和底部业务能力区同构；当前无可验证任务时可信空。 |
| 统一运营驾驶舱 | `reference-1280x720/operations-1280x720.png` | `current-1280x720/operations-1280x720.png` | 三栏比例同构；7 个正式业务切片可逐项选择，当前读取 219、挂接 210、待核对 9。 |
| 内容与活动工作台 | `reference-1280x720/content-campaign-1280x720.png` | `current-1280x720/content-campaign-1280x720.png` | 首屏恢复 `y=88`，左业务视图/中活动概览/右证据区及底部操作条同构；技术审计移入右栏独立滚动。 |
| 达人邀约驾驶舱 | `reference-1280x720/creator-growth-1280x720.png` | `current-1280x720/creator-growth-1280x720.png` | 首屏恢复 `y=88`，五阶段、达人档案、AI 分析三栏同构；治理审计移入右栏独立滚动。 |
| 多媒体内容生产 | `reference-1280x720/media-studio-1280x720.png` | `current-1280x720/media-studio-1280x720.png` | 指标、三内容页签、任务列表/详情/建议三栏同构；无正式数据时保持等待条件。 |
| 经营参谋 · 增长指挥中心 | `reference-1280x720/analyst-1280x720.png` | `current-1280x720/analyst-1280x720.png` | 开发态恢复生意探究 + 七经营页的八页签；生产仍默认关闭，命令能力未隐式开启。 |
| 价格治理驾驶舱 | `reference-1280x720/price-governance-1280x720.png` | `current-1280x720/price-governance-1280x720.png` | 顶部上下文、三页签、商品/任务链/数字同事三栏同构；无可用价格证据时失败关闭。 |
| 客户关系工作台 | `reference-1280x720/customer-1280x720.png` | `current-1280x720/customer-1280x720.png` | 客户切片/详情/条件三栏同构；真实源 54 条因同意或留存条件未闭合而不展示客户明细。 |

八个当前页面均实测 `innerWidth=clientWidth=scrollWidth=bodyScrollWidth=1280`，没有页面级横向溢出；公共侧栏从展开态 `main x=308/w=972` 折叠到 `main x=96/w=1184` 后仍为 `scrollWidth=1280`，再展开可恢复。

## 逐项功能复验

- 日常任务总控：6 个数字同事卡片可打开介绍浮层；浮层受视口约束，不与底部“明日预告”重叠。侧栏折叠/展开可工作。
- 统一运营：订单、订单明细、库存、履约、支付、售后事件、运营工单 7 个切片逐项选择后 `aria-pressed=true`；“分类事件”点击返回“当前业务条件不足，未触发业务操作”，没有死按钮或虚构写入。
- 内容与活动：活动策划、内容日历、日常模板 3 视图逐项激活；“生成方案”点击返回中文安全预检结果，未创建内容、预算或发布任务。
- 达人邀约：达人库、招募漏斗、商务签约、履约效果、长期关系 5 阶段逐项激活；“读取达人档案”返回可信空，不触发外部检索或邀约。
- 多媒体：种草文案、短视频、数字人直播 3 页逐项选中，始终只有 1 个对应 tabpanel。
- 经营参谋：生意探究、经营总览、驱动因素、问题诊断、增长计划、效果复盘、证据链、数据质量 8 页逐项选中，始终只有 1 个对应 tabpanel；生意探究为 GET-only，写入口为 0。
- 价格治理：同款价格治理、竞品比价、调度控制台 3 页逐项选中，始终只有 1 个对应 tabpanel。
- 客户关系：客户最小投影、客户分群、生命周期旅程、对话与批次 4 页逐项选中，始终只有 1 个对应 tabpanel。

## 代码与测试闭合

- 专项：`AnalystPage + ContentCampaignPage + CreatorGrowthPage`，`23/23` GREEN。
- Web 累计：`255 files / 2321 tests` GREEN。
- TypeScript：`tsc --noEmit` GREEN。
- 生产构建：`tsc -p tsconfig.json && vite build` GREEN，`359 modules transformed`。
- 已知警告：既有 React `act` 测试环境提示与 Vite 大 chunk 提示；没有新增失败。

## 安全与一致性结论

- 当前页面的数字来自真实 GET-only 读取或可信空；没有把视觉源演示数据、开发任务编号、技术方案编号写成业务任务。
- 开发模式无显式 Feature Flag 时只开放 `ecommerce.investigation.read` 供页面验收；测试与生产默认关闭，显式空值继续关闭，`ecommerce.investigation.commands` 必须显式配置。
- 本轮没有 Provider 调用、客户消息、发布、调价、退款、补偿、迁移、P01-P12 手工重放或其他外部副作用。
