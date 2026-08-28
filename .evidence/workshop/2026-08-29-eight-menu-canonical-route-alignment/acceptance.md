# 八菜单 canonical route 对齐验收

- 分支：`m1`
- 真实租户：`org-org/dev-project`
- 范围：只校准验收与 interaction-honesty 清单中的 canonical route；不修改安装、业务数据、SourceReadiness 或外部效果。

## 根因与改动

- 当前侧栏和 `/v1/ecommerce-workshop/modules` 共同声明：日常任务 `/workshop/cockpit`、达人邀约 `/workshop/creator-growth`、价格治理 `/workshop/price-governance`。
- 旧验收清单仍使用 `/workshop/task-cockpit`、`/workshop/creator-outreach`、`/workshop/pricing-governance`，直接访问会诚实显示“模块未安装”。
- 已将 `workshopAcceptance`、interaction-honesty manifest 及其测试统一到当前 canonical route；没有新增旧路由 alias。

## 测试

- acceptance、Shell、AppShell、interaction-honesty 专项：`24 passed`。
- interaction-honesty CI：`PASS (55 pages)`。
- Web 全量：`255` 个测试文件、`2314 passed`。
- TypeScript：GREEN。
- production build：GREEN；仅保留既有大 chunk 提示。

## 内置浏览器验收

- 从页面共享侧栏真实 anchor 逐个点击八个 canonical 菜单，不使用旧路由或猜测路由代替。
- 八页均进入对应 canonical URL，未出现“模块未安装”，每页 DOM 恰好一个 `h1`，横向溢出为 `0`。
- 日常任务、内容活动、统一运营、达人邀约、多媒体、经营参谋、价格治理、客户关系关键按钮/视图均可见；业务可见文案中未出现 `BI-W*`、`W*-*` 或 `AOS-*` 开发编号。
- 达人页确认“导入达人/新建邀约批次”，价格页确认“导出报告/新建监测策略”；旧入口继续 fail closed，不形成第二套路由权威。

## 1280×720 视觉稿对照补充

- 以仓内视觉基准截图逐页对照当前运行页：共享壳的 48px 顶栏、260px 左侧导航、主内容分栏、Tab/状态条、证据与动作区层级保持一致；真实空数据通过可信空卡片呈现，没有用视觉稿中的演示订单、达人、客户或经营指标冒充栖月汇事实。
- 日常任务页保留顶部指标/命令条、左右三位数字同事、中央任务流、右侧复盘和底部预告结构；当前六位数字同事均逐个打开过介绍浮层。
- 导购顾问浮层在 `1280×720` 视口的边界为 `x=437, y=245.98, width=330, height=229.52`；“明日预告”顶边为 `y=533.5`，浮层底边为 `475.5`，无覆盖。
- 内容活动、运营、达人、多媒体、经营参谋、价格、客户页均保持各自视觉稿的多栏业务工作区；较旧的视觉稿截图存在窄屏演示文案挤压，当前运行页没有复刻该缺陷。
