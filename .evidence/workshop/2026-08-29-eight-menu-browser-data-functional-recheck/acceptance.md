# 八菜单浏览器、视觉与真实数据复验

- 运行时：`m1@bcf4dc4a`，API PID `14251`，Web `127.0.0.1:5173`。
- 实际租户：`org-org/dev-project`；隔离 canary 未作为业务数据。
- 视觉基准：仓内 `foundry/html/evidence/2026-08-13-*` 八页正式截图。内置浏览器安全策略禁止直接打开 `file://`，未绕过；基准截图用于视觉比对，内置浏览器用于实际运行页与交互。

## 逐页运行结果

| 页面 | moduleId | H1 | 横向溢出 | canonical 状态 | 主要交互 |
|---|---|---|---:|---|---|
| 日常任务总控大屏 | `ecommerce.task-cockpit` | 1 | 0 | degraded，正式任务 0 | 日历、六数字同事浮层、重读、侧栏切换均工作 |
| 内容与活动工作台 | `ecommerce.content-campaign` | 1 | 0 | degraded，3 视图 | 三视图、生成/草稿/发布预检、重读均工作 |
| 统一运营驾驶舱 | `ecommerce.operations` | 1 | 0 | degraded，6/7 slice ready | 七切片、库存详情、动作预检、侧栏切换均工作 |
| 达人邀约与签约驾驶舱 | `ecommerce.creator-growth` | 1 | 0 | degraded，5 阶段 | 五阶段、达人档案/分析读取、重读均工作 |
| 多媒体任务全过程闭环工作台 | `ecommerce.media-studio` | 1 | 0 | degraded，3 视图 | 三类型、新建任务预检、内容计划跳转、重读均工作 |
| 经营参谋 · 增长指挥中心 | `ecommerce.analyst` | 1 | 0 | degraded，7 视图 | 七视图、今日方案、重读均工作 |
| 价格治理驾驶舱 | `ecommerce.price-governance` | 1 | 0 | degraded，3 视图 | 三视图、导出/新建预检、刷新均工作 |
| 客户关系工作台 | `ecommerce.customer` | 1 | 0 | degraded，4 视图 | 四视图、导入/新建触达预检、重读均工作 |

八页均无“正式读取失败”、`Internal Server Error`、开发波次编号或技术任务标题。代表性 Tab/阶段点击均引起 `aria`、选中 class 或正文变化，不是空点击；所有写入口只显示中文安全预检且未触发外部效果。

## 视觉比对结论

当前运行页保留视觉稿的全局深色图标栏、可折叠业务侧栏、紧凑顶栏、顶部指标/上下文带、左中右三栏、状态色、底部上下文与 1280×720 首屏比例。正式业务数据为空时，以同一结构中的可信空态替换视觉稿演示卡片；未复制视觉稿中的 GMV、客户、达人、活动或任务示例数字。侧栏折叠、展开、恢复均无横向溢出；总控六数字同事浮层实际可开且不遮挡固定底栏。

## 数据追溯

八个 canonical GET 均返回 200 与对应 schema。统一运营当前有界页来源/挂接/待核对为 `219/210/9`，库存为 `50/41/9/0`；其他领域在正式 authority 未形成时保持可信空，不用技术方案任务或模拟业务记录填充。

结论：`EIGHT_MENU_RUNTIME_VISUAL_STRUCTURE_FUNCTION_DATA_TRACE_GREEN / TRUSTWORTHY_EMPTY_PRESERVED / NO_EXTERNAL_EFFECT / NO_RELEASE`。
