# 八菜单浏览器功能与 CustomerLite 真实来源验收

- 日期：2026-08-29
- 分支：`m1`
- 真实租户：`org-org/dev-project`
- 隔离 canary：`dev-org/dev-project`
- 边界：只读业务探针与页面安全预检；未手工运行或重放 P01～P12，未解析客户身份，未创建业务记录，未触发 Provider、发布或外部副作用

## 浏览器逐页验收

内置浏览器逐页打开并实际操作以下 canonical 路由：

1. `/workshop/cockpit`
2. `/workshop/content-campaign`
3. `/workshop/operations`
4. `/workshop/creator-growth`
5. `/workshop/media-studio`
6. `/workshop/analyst`
7. `/workshop/price-governance`
8. `/workshop/customer`

八页均命中正确 active 导航、恰好一个一级标题、横向溢出为 `0`、页面内 alert 为 `0`。共享侧栏已实测折叠并恢复。内容、运营、达人、媒体、经营参谋、价格和客户的页签/业务视图逐项点击可切换；“查看今日方案”会选择增长计划面板。

总控页六数字同事卡片均已逐个打开介绍浮层；浮层保持在工作区视口内，不遮挡明日预告，包含“专业能力、工作边界、常用 Agent、当前状态”。页面没有放大镜或日历巨型空态图标。

八页主动作逐项点击：空任务下达给出输入校验；新建活动、新建处理、新建邀约批次、新建内容任务、新建监测策略、新建触达任务均只打开安全预检并明确未创建记录或触发外部操作。经营参谋“查看今日方案”只切换到现有只读增长计划视图。

## 栖月汇真实数据链

- 自然 Cron：`P08-customer-lite-qyh`
- 启动时间：`2026-08-29T01:00:09.034932+00:00`
- 自然运行结果：成功，写入 `54`
- `org-org/dev-project`：正式 CustomerLite 来源 `54`，页面披露条目 `0`
- `dev-org/dev-project`：不存在对应自然成功运行，reader 失败关闭
- 浏览器客户页：四个视图均显示“正式来源 54”；CustomerLite 轴显示 exact source window，其他同意、分群、旅程、对话与触达轴继续等待必要条件；页面明确显示“允许披露 0 条”，不出现姓名、手机号、OpenID 或其他受保护身份信息

## 测试证据

- 客户 parser、客户页与总控浮层专项：`30/30`
- ecommerce Workshop API 累计：`201/201`
- Workshop Web/API parser 累计：`304/304`
- TypeScript：`tsc --noEmit` GREEN
- 真实只读探针：主租户 `54/0`（来源/披露），隔离 canary 失败关闭

## 方案一致性结论

实现保留“原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图”的既有结构。CustomerLite 来源成功只水合客户页的来源轴和守恒计数，不替代同意、用途、留存、分群、旅程或触达 authority；因此页面可工作、数据可追溯，同时没有以来源可读冒充客户可披露或可触达。
