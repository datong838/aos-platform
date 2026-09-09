# AR2-7E 八工作台入口矩阵 · 入场前施工清单

日期：2026-09-10  
基线：`m1@03048e86`  
状态：`PRE_ENTRY_ONLY_WAITING_FOR_AR2_7D_PRIME_REVIEW`

## 1. Rules 与进入条件

- 权威顺序：closure manifest、`dynamic-reference-phases.json`、231-6、当前 `m1` 已提交代码与新鲜验证。
- 231-6 第 160 条要求 7D 的累计回归、资产控制浏览器、Prime 复审和 authority CAS 全部闭合后才能进入 7E。当前 Prime 登录态阻塞，因此本文件只整理输入，不修改 7E 产品代码、不生成 7E GREEN。
- 7E 只验证同一已安装目录、权限和 slot registry 驱动的八工作台入口与隔离浏览器矩阵。closure manifest 第 130、148 行把真实 `org-org/dev-project` 栖月汇只读数据接入固定在 A0-V/A1；7E 不提前读取真实租户数据，也不以历史截图冒充当前验收。
- `dev-org/dev-project` 仅作负向租户 canary。写操作只允许后续施工方案明确列出的隔离内部记录；Provider、费用、真实发布、真实业务 mutation、共享/生产迁移和 push 均为 0；`230 L0` 继续挂起。

## 2. 当前实现基线

- 入口：`apps/web/src/pages/s2/ecommerce/routes.tsx` 只返回 `EcommerceWorkshopHost`。
- 安装目录：`EcommerceWorkshopHost.tsx` 用 `catalog.modules` 匹配当前路径；legacy 只重定向到当前安装模块；目录 loading/forbidden/failed/empty 均失败关闭。
- 导航：`InstalledModuleNavigation.tsx` 只遍历 `catalog.modules`；空目录或读取失败时没有静态八菜单旁路。
- 八个页面组件已经存在：Task Cockpit、Operations、Content Campaign、Creator Growth、Media Studio、Analyst、Price Governance、Customer。
- 组件测试已覆盖八条主路由的完整共享侧栏、唯一 active、折叠恢复、路由切换滚动复位、页面顶部语义以及未接通动作的原生禁用；这些测试不能代替三视口真实浏览器逐页点击。

## 3. 7E 浏览器矩阵

每页在 `1280×720`、`1440×900`、`1920×1080` 三档视口执行同一脚本，共 24 个页面视口单元；每个单元必须记录页面错误、控制台错误、500 响应、请求方法/路径、水平溢出、主内容和侧栏滚动、唯一 active 项与截图。

| 模块 | 路由 | 页面专项 |
|---|---|---|
| 日常任务总控 | `/workshop/cockpit` | 推荐任务回填、六数字同事浮层、十个共享智能体/能力、明日预告双栏、今日复盘、AI 改进建议、经验沉淀 Wiki；读取失败与空态分离 |
| 内容与活动 | `/workshop/content-campaign` | 三主页签、筛选、内容排期/任务计划、模板状态、刷新和内部草稿准备；外部发布为 0 |
| 统一运营 | `/workshop/operations` | 正式业务切片、Case 工作区、筛选/搜索、详情浮层、内部处理提案与回读；不执行真实运营动作 |
| 达人邀约 | `/workshop/creator-growth` | 五阶段、筛选、候选/合同/履约/关系空有数据态、内部准备草稿；不披露联系方式、不外发邀约 |
| 多媒体生产 | `/workshop/media-studio` | 三媒体类型、任务/交付候选、筛选/刷新、内部任务和发布审批草稿；Provider 与外部发布为 0 |
| 经营参谋 | `/workshop/analyst` | 实体选择、Case/Run、方案建议、证据/质量页签、刷新与回读；7E 使用隔离 fixture，真实栖月汇只读数据留 A0-V |
| 价格治理 | `/workshop/price-governance` | 三页签、质量/研究/处置只读视图、刷新、禁用真实调价/外部通知 |
| 客户关系 | `/workshop/customer` | 四页签、同意/目的/留存排除统计、审计状态、刷新；不披露客户明细、不发送触达 |

## 4. 正反入口与状态矩阵

1. 正向目录：八个模块均来自同一当前 installation/catalog 响应，module artifact hash、installation revision、lock revision 与 readiness 可回读；八条路由各有且只有一个 active 导航。
2. 空目录：八条直接 URL 全部显示“模块未安装”，侧栏不出现任何 Workshop 模块链接。
3. 目录失败/403：保留失败或无权限状态和重试动作，不回退静态菜单或旧页面。
4. 模块不可用：stale/degraded/unknown/blocked 状态保留只读内容和 blocker；所有命令按服务端 `allowedCommands` 与页面正式依赖失败关闭。
5. 旧入口：仅在当前 catalog 的 `legacyRoutes` 明确声明时重定向；卸载、禁入或旧 generation 后不得重定向到旧静态页面。
6. 租户 canary：同一 fixture 标识在 `dev-org/dev-project` 不得读到正向目录、页面数据、内部草稿或 Receipt。

## 5. 预计文件范围

- 方案与证据：`.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-*.md|json|mjs|png`。
- 浏览器验收脚本：新增同目录 `ar2-7e-eight-workbench-browser.mjs`，复用现有 Playwright/Chrome 和只读 API route fixture 方式，不修改浏览器全局配置。
- Web 测试仅在浏览器发现确定性缺陷时最小修改：
  - `apps/web/src/components/workshop/EcommerceWorkshopHost*.tsx`
  - `apps/web/src/components/workshop/InstalledModuleNavigation*.tsx`
  - `apps/web/src/components/workshop/{TaskCockpitPage,OperationsPage,ContentCampaignPage,CreatorGrowthPage,MediaStudioPage,AnalystPage,PriceGovernancePage,CustomerPage}*.tsx`
  - `apps/web/src/shell/AppShell.workshop.test.tsx`
- 不预设后端改动；若页面合同与已提交 API 不一致，先追加确定性缺口、Owner、文件和退出条件，再编码。

## 6. 执行与退出顺序

1. 7D Prime PASS 后写 7D 最终证据并执行 AOS-000571 的 authority CAS；保持同一 AR2-7 Task/Lease。
2. 固定 7E HEAD、目录/权限/slot fixture、视口、浏览器主路径和零副作用断言；先运行 Web 专项/全量/build。
3. 执行 24 单元八页矩阵、空目录、403/失败、旧入口、跨租户 canary；失败最多修复后重跑受影响单元与全量，不切换控制通道。
4. 回读截图、JSON、网络记录、console/page error、按钮和浮层结果；运行 closure/memory/diff check 与 Prime 增量复核。
5. 只有 7D+7E 累计条件全部满足，才写唯一整波退出标记 `AR2_HOST_WIRING_CUTOVER_PLUGGABILITY_BROWSER_ACCEPTANCE_GREEN`，完成同一 Task/Lease 的最终 Delivery Receipt/CAS，并自动进入 A0-V。
