# Workshop 主工作台八菜单视觉纠错审计

## 当前结论

- Task：`S8-VISUAL-PRIMARY-EIGHT-MENU-CORRECTION`
- scope：Workshop 八个一级业务菜单，不是经营参谋内部八个 Tab。
- source truth：八个 `docs/palantier/foundry/html/workshop-*.html` 页面。
- 当前结果：RED；尚未满足 1:1 视觉封板。

## 已确认 P0/P1

1. P0：任务总控页当前结构与 `workshop-task-cockpit.html` 不同。source 的 KPI 带、任务下达条、执行组/任务流/策划组三栏、共享 Skill 带和明日预告未按同位结构落地。
2. P1（已修正，待三视口累计复验）：经营参谋公共顶部区域曾发生挤压。标题、面包屑、渠道选择、负责人标签与“查看今日方案”共用横向轨道，原负责人胶囊比 source 多占约 29px；现已按 source 密度收敛并保持“未绑定”真值。
3. P1：先前证据把经营参谋内部八 Tab 当成 Workshop 八个一级菜单，验收 scope 错误。

## 修复顺序

- V0：公共 Shell 顶部双层几何、最小高度、控件尺寸、断点换行与状态条独占轨道。
- V1：任务总控页。
- V2：统一运营驾驶舱。
- V3：内容与活动工作台。
- V4：达人邀约驾驶舱。
- V5：多媒体内容生产。
- V6：经营参谋。
- V7：价格治理驾驶舱。
- V8：客户关系工作台。
- V9：八页三视口、功能/后端累计回归与交付闭环。

## 证据要求

每页 source/current 必须在相同视口和相同页面状态下进入同一比较输入；修复后重新截图并重新判定。P0/P1/P2 未全部清零前不得写 `passed`。

## V0 公共顶部壳最终几何复验

- 实测视口：`1280×720`。
- 经营参谋 topbar：`x=48/y=0/w=1232/h=48`；标题 `26px/39px`、面包屑和右侧控件恢复为与 source 一致的单轨结构。
- 负责人标签：source `w≈136.75px`；当前 `w=137.69/clientW=136/scrollW=136`，完整显示“经营参谋（owner 未绑定）”，无 ellipsis。
- 右侧控件组由 `438.34px` 收敛为 `410.02px`（source `≈409.09px`），与左侧标题组重叠为 `0`；document `clientWidth=scrollWidth=1280`。
- 状态条从 `y=48` 开始进入 972px 内容轨，不再挤压顶部标题行；窄视口仍保留显式断点换行。
- 截图：`v14-analyst-1280x720.png`；source：`source-analyst-1280x720.png`。
- 专项：八页组件与 AppShell `65/65` GREEN；TypeScript、生产构建与 `git diff --check` GREEN。

V0 的“顶部挤压/负责人截断”缺陷已在 1280 首档关闭；不得据此推导其余视觉细节已经 1:1。

## V1 任务总控首轮复验

- source：`foundry/html/workshop-task-cockpit.html` 与用户提供的 source 截图。
- 当前：`v16-task-cockpit-1280x720.png`。
- 实测几何：topbar `48px`；二级图标栏 `48px`；KPI `72px`；只读指令栏 `51px`；主体 `428px`；共享 Skill `50px`；审计折叠栏 `37px`。
- 页面横向宽度：document `clientWidth=1280/scrollWidth=1280`，无页面级横向溢出。
- 已恢复 source 的 KPI、指令条、执行组—任务流—策划组—复盘四列、共享 Skill 与明日预告结构；数据只消费当前 canonical Task/Run/blocker，缺失事实显示“未知/待验证”。
- KPI 带现为与 source 同数量的 7 个槽位；新增槽只展示 canonical `pending` 数量。纠正了把 `Task.priority` 冒充执行进度的语义错误：仅 `completed` 显示 100%，其余显示虚线未知进度；浏览器回读 `15 complete / 5 unknown / priorityWidthUsed=false`。
- 原运行、发布与审计功能保留在原生 `details` 中，默认收起；视觉命令 input/“下达”按钮保持 disabled，无新增 command 或副作用。
- 专项：`TaskCockpitPage + AppShell` 共 `22/22` GREEN；TypeScript GREEN。

V1 当前从结构性 P0 转为细节 P1/P2 复审；还需在 V9 用 source/current 同输入关闭字体、间距与三视口差异。V2–V8 尚未完成，因此整体结论不变。

### V16 顶部指标带复核

- 视觉稿同位的 `73px` 指标带已改为六个等宽事实槽加一个截止槽；当前 `x=308/y=48/w=972/h=73`，`scrollWidth=clientWidth=972`。
- 原完整日期时间造成指标带内部 `989/972` 溢出的顶部挤压已消除；评估时刻压缩为 `HH:mm`，日期保留在同槽次级文本，完整 evaluated/cutoff 仍保留在 `title` 可回读语义中。
- 下达与筛选条仍为 `x=308/y=121/w=972/h=53`，没有与指标带或右侧按钮重叠；页面文档宽度仍为 `1280/1280`。
- 专项 `TaskCockpitPage + AppShell` 为 `23/23` GREEN。V16 只关闭顶部挤压，不把真实 canonical Task 内容差异判成像素封板。

## V2 统一运营驾驶舱首轮复验

- source：`foundry/html/workshop-app-order.html`，核心几何为 `340px / flex / 320px` 三栏。
- 当前：`v2-operations-1280x720.png`。
- 公共二级导航由 `260px` 展开栏收敛为 `48px` 图标栏；内容区 `x=96/w=1184`，document `clientWidth=1280/scrollWidth=1280`，无页面级横向溢出。
- 指标带由两行恢复为单行：`x=96/y=88/w=1178/h≈90.45`；只读边界条 `h=69`；三栏主体从内容撑高改为固定首屏 `520px` 与栏内独立滚动。
- 右栏专业贡献归因由四个极窄横排卡改为纵向四步链，关闭逐字断行问题；`unknown` 仍保留，不伪造 AgentRun/SkillBinding/LogicRevision。
- 运营页与 AppShell 专项 `8/8` GREEN；TypeScript GREEN；`git diff --check` GREEN。

V2 已关闭“公共壳层过宽、指标折行、右栏逐字断行”的 P1；仍须在 V9 对 source/current 同视口复核细节。V3–V8 尚未完成，因此整体结论不变。

## V3 内容与活动工作台首轮复验

- source：`foundry/html/workshop-content-campaign.html`，核心几何为 `40px` 三 Tab、`280px / flex / 340px` 三栏。
- 当前：`v3-content-campaign-1280x720.png`。
- 已移除首屏上方重复的大标题、模块上下文、状态卡与两行指标占位；内容体从 `y≈650` 提升至 `y=88`。
- 当前几何：toolbar `x=96/y=48/w=1178/h=40`；board `x=96/y=88/w=1178/h=595`；左栏 `280px`、中栏 `558px`、右栏 `340px`；页面无横向溢出。
- 三个视觉 Tab 已对应“活动策划 / 内容日历 / 日常模板”并驱动真实 canonical slice 选择；左栏修正为纵向列表，未再受 `1280` 断点的三列规则影响。
- 中栏恢复视觉稿的策划助手输入槽，但内容只陈述 authority 不足，textarea 只读、生成按钮 disabled；未注入七夕活动、预算、GMV 或发布成功等演示事实。
- 原数量守恒、只读边界与截止面移入原生 `details` 审计区，默认收起但未删除；右栏继续展示 exact blocker 和专业贡献归因。
- 内容、运营与 AppShell 累计专项 `11/11` GREEN；TypeScript 与 `git diff --check` GREEN。

V3 已关闭“页面体被通用诊断卡推到首屏下方、左栏横排碎裂、缺少视觉 Tab”的 P1；仍须 V9 联合 source/current 清零细节。V4–V8 尚未完成，因此整体结论不变。

## V4 达人邀约驾驶舱首轮复验

- source：`foundry/html/workshop-creator-outreach.html`，核心几何为五 Tab 与 `280px / flex / 340px` 三栏。
- 当前：`v4-creator-growth-1280x720.png`。
- 当前几何：toolbar `x=96/y=48/w=1178/h=40`；board `x=96/y=88/w=1178/h=595`；三栏分别 `280/558/340px`，document 无横向溢出。
- “达人库 / 招募漏斗 / 商务签约 / 履约效果 / 长期关系”五 Tab 已连接现有五阶段 selection；左栏保持纵向阶段列表，中央显示 workflow phase 和账本，右栏显示当前 exact blocker。
- 双轴、专业贡献、生命周期与三模块 closure 未删除，移入默认收起的原生审计区；外部触达、寄样、签约、佣金动作仍不存在。
- 达人、内容、运营与 AppShell 累计专项 `15/15` GREEN；TypeScript 与 `git diff --check` GREEN。

V4 已关闭“首屏被治理卡推迟、缺少五 Tab、三栏比例失真”的 P1；仍须 V9 联合 source/current 清零细节。V5–V8 尚未完成，因此整体结论不变。

## V5 多媒体内容生产首轮复验

- source：`foundry/html/workshop-media-studio.html`，首屏核心是媒体类型 Tab 与左/中/右生产三栏。
- 当前：`v5-media-studio-1280x720.png`。
- 当前几何：toolbar `x=96/y=48/w=1178/h=40`；Tab `y=88/h=44`；panel `y=132/h=551`；三栏为 `300px / 518px / 360px`（`1280` 断点降为 `250px / 628px / 300px`），仅栏内纵向滚动，document 无横向溢出。
- “种草文案 / 短视频 / 数字人直播”连接现有 canonical slice；生命周期、readiness/authority 与 blocker 分列展示。全过程治理、累计验收、发布候选、Provider Job 与费用结算未删除，移入默认收起的审计区。
- Provider、发布、结算和外部副作用仍无写入口；authority 缺失按原值失败关闭，不注入演示素材或成功状态。
- Media、Customer 与 AppShell 专项 `19/19` GREEN；TypeScript 与 `git diff --check` GREEN。

V5 已关闭“一列纵向堆叠、首屏看不到三栏工作区”的 P1；媒体卡片密度、边框和字号仍须 V9 同视口复审。

## V6 经营参谋顶部与可信空复验

- source/current 同输入：`comparison.html` 与 `comparison-full.png`，其中每一对图片都是 `1280×720` 同视口证据。
- `1280×720` 实测：topbar `x=48/y=0/w=1232/h=48`；aside `x=48/y=48/w=260/h=672`；content `x=308/y=48/w=972/h=672`；document 无横向溢出。
- 标题、面包屑、渠道、负责人和“查看今日方案”完整可见；负责人不再截断，状态条从 `y=48` 进入内容轨。
- canonical Case/Run 不存在时继续展示可信空，不把 source 演示 Case、商品、门禁或经营数字写入当前租户。

V6 已关闭用户截图中的顶部挤压和负责人截断；其余页面细节仍按 V9 的 source/current 对照逐项判定。

## V7 价格治理驾驶舱首轮复验

- source：`foundry/html/workshop-price-governance.html`，核心结构为“同款价格治理 / 竞品比价 / 调度控制台”Tab 与三栏治理工作区。
- 当前：`v7-price-governance-1280x720.png`。
- 当前几何：toolbar `y=48/h=40`；Tab `y=88/h=44`；panel `y=132/h=551`；三栏 `280/558/340px`，无页面级横向溢出。
- 现有价格 authority、规则与 blocker 保持只读；治理处置、补救、闭环和贡献证据移入默认收起审计区，不新增调价、发布或真实业务写入。
- 标签与布局专项测试 GREEN，并进入八页累计回归。

V7 结构性 P1 已关闭；细节仍进入 V9。

## V8 客户关系工作台首轮复验

- source：`foundry/html/workshop-customer.html`，核心结构为四 Tab 与三栏客户工作区。
- 当前：`v14-customer-1280x720.png`。
- 当前实测：topbar `48px`、toolbar `40px`、Tab 从 `y=88` 开始、三栏主体占据首屏；document `clientWidth=1280/scrollWidth=1280`。
- 当前真实 GET 失败时不再退化为占满首屏的通用错误卡，而是保留客户最小投影/同意依据/依赖证据三栏；所有字段明确为 `unknown` 或 exact authority 缺失，不制造客户、联系方式、同意状态或数量 0。
- 新增失败态三栏骨架测试；Customer `4/4` GREEN，并进入累计回归。

V8 已关闭“读取失败后页面结构完全偏离视觉稿”的 P1；真实客户内容仍受 authority 门保护，V9 继续做视觉细节复核。

### V14 顶部与三栏几何复核

- 顶部上下文条已收敛为视觉稿同位的 `x=308, y=48, w=972, h=40`，`scrollWidth=clientWidth=972`，不存在顶部挤压或横向溢出。
- 主面板从 `y=88` 起，左侧任务列宽 `280px`；四个真实只读视图改为纵向任务列，单项高度 `42px`，不再以横向四 Tab 挤占首屏。
- 中栏仍只展示服务返回的 readiness，右栏仍只展示依赖与下一证据；顶部数量全部为 `unknown`，没有复制视觉稿中的演示客户、数量或触达任务。
- 页面文档宽度 `1280/1280`，无横向溢出。V14 关闭客户页顶部挤压 P0，但与视觉稿的内容密度、卡片细节和底部动作区仍存在差异，因此整体视觉审计继续为 RED。

## V9 当前判定

- 八页已经形成 `comparison.html` / `comparison-full.png` 同输入：左侧 source、右侧 current，16 张图片均为 `1280×720` 且已确认可读。
- 新鲜累计回归：八页组件、经营探究与 AppShell 共 `65/65` GREEN；TypeScript `--noEmit`、生产构建与 `git diff --check` GREEN。现有 React `act(...)` 警告未转化为测试失败，但继续作为测试环境噪声记录。
- 八路由 `1280×720` 顶栏均为 `48px`；公共 aside `260px`、content `972px`，实测 `scrollWidth=clientWidth=1280`，document/body 均无横向溢出。
- source/current 对照确认公共骨架、顶部轨道、侧栏宽度、主要纵向起点与三栏比例已对齐；当前租户真实/可信空内容不复制 source 演示数据。
- 六个非 Cockpit/Analyst 一级页已补回各自 source 对应的标题/面包屑、搜索框、上下文标签和操作按钮位置；会引发业务写入的视觉按钮保持 `disabled`，只复刻视觉层，不绕过只读门。六页实测左组/搜索/操作区均无重叠，`scrollWidth=clientWidth=1280`。
- 最新证据：`v16-task-cockpit-1280x720.png`、`v11-operations-1280x720.png`、`v13-{content-campaign,creator-growth,media-studio,price-governance}-1280x720.png`、`v14-{analyst,customer}-1280x720.png`；价格/客户面包屑重复已在 v12 关闭，分析/客户顶部挤压已在 v14 关闭，任务总控指标带溢出已在 v16 关闭。
- 价格治理补齐 source 型只读上下文条：品牌/SKU、owner/协作者、策略 revision、待复核视图与刷新入口同轨；实测 `x=308/y=48/w=972/h=55`，Tab `y=103/h=43`，panel `y=146`，无横向溢出。`3 个视图待复核`来自三个 canonical blocked view，不冒充价格异常数量。
- 已确认不能把 source 演示业务数据复制进真实租户，也不能用不同视口截图得出 pixel-perfect pass。
- 当前仍有可见细节差异（任务卡密度、部分英文 authority 文案、媒体卡片间距、各页字号/边框/色阶），均继续作为 P1/P2 处理。

`final result: failed`

## V17 内容与活动可信空结构密度复验

- source/current 同为 `1280×720`；最新当前证据为 `v17-content-campaign-1280x720.png`，并已替换 comparison 中的旧 V13 图片引用。
- 中栏按 source 的垂直信息密度补齐“AI 策划结论 → 活动概览 → 底部审批操作”三段：助手结论 `x=513/y=218/w=466/h≈88.6`，活动概览 `x=513/y≈320.6/w=466/h≈285.5`，底部操作条 `x=498/y≈610.5/w=496/h≈70.5`。
- 三栏保持 `190 / 502 / 280px`，toolbar `x=308/y=48/w=972/h=40`，board `x=308/y=88/w=972/h=595`，document `clientWidth=scrollWidth=1280`；没有顶部挤压或页面级横向溢出。
- 所有同位写操作均为 disabled；页面未复制七夕活动、预算、GMV、毛利、风险建议或发布成功等演示事实。canonical authority 不可用时明确显示“尚未形成可审阅方案 / 等待 exact authority / 失败关闭”。
- 测试先红后绿；内容页专项 `3/3`、八菜单累计专项 `65/65`、TypeScript、production build 与 diff-check 全部 GREEN。既有 React `act(...)` 警告及 Vite 大 chunk 警告未转化为失败。

V17 关闭内容页中栏可信空结构密度 P1；八页仍有字号、色阶、卡片密度及多视口差异待清零，整体结论继续为 `failed`。

## V18 多媒体可信空三栏语义复验

- 最新当前证据为 `v18-media-studio-1280x720.png`，comparison 已切换该图；source/current 均为 `1280×720`。
- 顶部上下文、四指标、三 Tab 与 panel 继续保持 `y=48/104/194/238` 的连续轨道；panel `x=308/w=972/h=482`，三栏可用宽度为 `240/408/300px`，document `clientWidth=scrollWidth=1280`。
- 左栏由整页 reason code 改为“文案任务 / 任务列表 / 可信空卡 / 折叠原始 blocker”；中栏增加“等待生产上下文”摘要后继续展示全部 target axes；右栏增加“内容官建议 / 尚无可回链内容建议”后保留原始 blocker。reason code、dependency 与 required action 没有删除。
- 页面没有复制七夕专题、banner 文案、CTR、GMV、Provider 结果或已产出状态；真实 `unknown/blocked` 保持原值。
- Media 专项 `9/9` 与 TypeScript GREEN；累计回归和 production build 在本提交前再次执行。

V18 关闭多媒体失败态“英文大段撑满三栏、缺少中文工作区层级”的 P1；右栏内容密度、target 卡字号与三视口仍进入后续清零，整体结论继续为 `failed`。
