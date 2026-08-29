# Workshop 八菜单当前浏览器、功能与数据追溯验收

- Task：`WORKSHOP-EIGHT-MENU-CURRENT-BROWSER-TRACEABILITY-20260829`
- 分支：`m1`
- 正式租户：`org-org/dev-project`
- 隔离 canary：`dev-org/dev-project`
- 当前浏览器主视口：`1280×720`
- 边界：只读 canonical GET 与页面安全预检；未手工运行/重放 P01～P12，未调用 Provider，未创建演示业务记录，未产生业务写入、外部副作用、迁移或发布。

## 当场关闭的确定性缺陷

1. 日常任务总控大屏六数字同事浮层：固定浮层时同步锁定同事身份，点击/键盘激活后复位共享主内容到顶部；focus 预览不移动视口。浏览器确认点击“导购顾问”后浮层标题稳定为“导购顾问”，`scrollTop=0`，顶部指标与明日预告均未被遮挡。
2. 统一运营驾驶舱业务按钮：`管理 SLA`、`自动化 Kill` 分别改为 `管理服务时限`、`停止自动化`；六个动作逐项点击均返回中文安全预检，旧英文标签不再出现在当前页面。

## 八菜单浏览器矩阵

| 页面 | 实际点击 | 几何与文案 | 结果 |
|---|---|---|---|
| 日常任务总控大屏 | 状态筛选、重新读取、日历往返、侧栏折叠恢复、六数字同事浮层、下达预检 | 单 H1、溢出 0、浮层不串位/不遮挡 | GREEN |
| 内容与活动工作台 | 三主视图、三业务切片、生成/保存/重新生成/两处批准发布/新建活动 | 单 H1、溢出 0、全部业务文案中文 | GREEN |
| 统一运营驾驶舱 | 七切片、重新读取、六业务动作 | 单 H1、溢出 0、六动作中文安全预检 | GREEN |
| 达人邀约驾驶舱 | 五主视图、五业务阶段、检索、三分群筛选、导入/新建批次 | 单 H1、溢出 0、主业务区无开发编号 | GREEN |
| 多媒体内容生产 | 三媒体类型、查看内容计划、新建内容任务、重新读取 | 单 H1、溢出 0、跳转与预检均有可见反馈 | GREEN |
| 经营参谋 · 增长指挥中心 | 八分析视图、查看今日方案、两处重新读取 | 单 H1、溢出 0、今日方案准确落到增长计划 | GREEN |
| 价格治理驾驶舱 | 三业务视图、导出报告、新建监测策略、刷新数据 | 单 H1、溢出 0、安全预检可见 | GREEN |
| 客户关系工作台 | 四业务视图、导入客户、新建触达任务、重新读取 | 单 H1、溢出 0、页面 PII 模式匹配数 0 | GREEN |

视觉复审以用户提供的视觉稿截图、仓库对应视觉蓝图 HTML/CSS 和当前内置浏览器截图为同输入依据；当前页均保持视觉稿的密集白底控制台、细边框、低圆角、固定侧栏、顶部工具区和三栏/分栏信息结构。内置浏览器安全策略拒绝直接导航本地 `file://` 蓝图，因此没有用绕过方式伪造浏览器 source 页面；实际产品八页仍全部在内置浏览器逐页截图和点击。

## 正式数据与隔离

| canonical GET | 业务视图数 | 来源/挂接 | 所需条件 | 正式租户结果 |
|---|---:|---:|---:|---|
| `views/task-cockpit` | 任务 0 | 0 / 0 | 2 | 可信空 |
| `views/content-campaign` | 3 | 0 / 0 | 3 | 可信空 |
| `views/operations` | 7 | 219 / 210 | 1 | 6 可读、1 待补条件 |
| `views/creator-growth` | 5 | 0 / 0 | 5 | 可信空 |
| `views/media-studio` | 3 | 0 / 0 | 3 | 可信空 |
| `views/analyst` | 7 + 生意探究 | 0 / 0 | 7 | 可信空 |
| `views/price-governance` | 3 | 0 / 0 | 3 | 可信空 |
| `views/customer` | 4 | 每视图 54 / 0 | 每视图 5 | 正式来源 54，允许披露 0 |

八个 endpoint 对 `dev-org/dev-project` 均返回 `404 NOT_FOUND / Workshop module is not installed`。客户响应与页面均未出现 phone、mobile、email、address 字段或值。

## 测试门

- `TaskCockpitPage.test.tsx`：`17/17` GREEN。
- `OperationsPage.test.tsx`：`2/2` GREEN。
- 运营后端命令与 API 专项：`22/22` GREEN。
- Web 全量：`256 files / 2324 tests` GREEN。
- TypeScript：GREEN。
- production build：GREEN，`362 modules transformed`；仅保留既有 chunk-size warning。
- Workshop + SourceReadiness API 累计：`241 passed`；仅保留既有 Pydantic/Starlette warnings。

## 结论

`CURRENT_BROWSER_FUNCTION_DATA_TRACEABILITY_GREEN_NO_EXTERNAL_EFFECT`。该结论证明当前八菜单视觉结构、交互反馈、前后端只读合同和租户隔离没有倒退；不把可信空补成演示数据，也不外推为 SourceReadiness 全绿、真实试点、外部动作或发布授权。
