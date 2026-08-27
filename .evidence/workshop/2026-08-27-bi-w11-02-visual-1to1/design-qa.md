# BI-W11-02 八菜单精确 1:1 视觉审计

## 审计边界

- source visual truth：`docs/palantier/foundry/html/workshop-analyst.html`
- 当前实现：`http://127.0.0.1:5173/workshop/analyst`
- 真实产品租户：`org-org/dev-project`
- 本轮状态：当前运行、只读、`unknown` 失败关闭；未执行真实 Source read、业务写入、Provider、迁移或发布
- 主比较视口：浏览器当前实际 `1280×720`；`1280×800 / 1440×900 / 1920×1080` 在整改后逐菜单重新捕获

## 新鲜基线证据

| 对象 | 当前运行截图 | 状态 |
| --- | --- | --- |
| source · 生意探究 | `baseline/source-inquiry-1440.png` | 原始视觉稿活动态 |
| implementation · 生意探究 | `baseline/current-inquiry-1440.png` | `org-org/dev-project` 当前只读失败关闭态 |

文件名保留最初计划中的 `1440` 标记，但本轮浏览器回读确认图片实际捕获画布为 `1280×720`；因此它们只能作为差异基线，不能作为 `1440×900` 最终证据。最终证据必须重新设置并回读视口后捕获，禁止沿用错误标注。

## 首轮同输入差异清单

### P0

1. 页面整体明暗体系不一致：source 为浅色工作台（`body rgb(240,242,245)`、白色二级导航与白色内容面），implementation 为深色工作台（`body rgb(2,6,23)`、二级导航 `rgba(15,23,42,.92)`）。这不是允许的产品文案差异，当前不能称为 1:1。
2. 当前实现将产品上下文、技术上下文与失败关闭摘要置于八菜单之前，导致 Tab 从 source 的 `y=84` 下移到 implementation 的 `y≈425.30`；主任务首屏层级与比例完全不同。

### P1

1. source Tab 为白底单行横向导航：容器 `x=308, y=84, w=972, h=39, padding=0 20px`；活动 Tab `padding=9px 14px`、`font-size=12px`、蓝色下边线。implementation Tab 为八列卡片网格：`x=340, y≈425.30, w=902, h=62, gap=6px`，组件结构、尺寸、内容起点和视觉密度均不一致。
2. source 主内容从 `x=308` 开始，内容内边距后首卡片 `x=328`；implementation Workshop 容器从 `x=340` 开始且宽 `902`，左右内边距和有效内容宽度不同。
3. source 二级导航为 `x=48, y=48, w=260, h=672` 白底；implementation 几何尺寸相同但为深色，并继承不同文字色、选中态、边框与图标表达。
4. source 生意探究首屏有案例条、三阶段轨道和工作区骨架；implementation 在 `unknown` 状态下没有同层级同密度的安全占位骨架。整改必须保留失败关闭事实，使用同构的可信空/阻断表达，不能伪造成功数据。

### P2

1. 字号、行高、字重、颜色 token、边框、圆角、阴影、内外边距尚未逐组件清零；需要以 source computed style 为冻结值逐项回填。
2. 八菜单在 `1280×800 / 1440×900 / 1920×1080` 的换行、横向滚动、固定导航与内容高度尚未形成新鲜证据。
3. 八菜单的键盘切换、状态标签、错误恢复与对应 GET contract 尚需在视觉整改后累计复验，不能由旧 S8 截图代替。

## 整改顺序

1. 路由级浅色 Shell 与 48/260/48 几何冻结。
2. Workshop 标题/上下文收纳，不改变信息与失败关闭语义，但恢复 source 的首屏层级和密度。
3. 八菜单 Tab 改为 source 单行导航规格。
4. 生意探究可信空/blocked 骨架对齐案例条、阶段轨道、工作区。
5. 其余七菜单逐页对齐卡片、表格、筛选、状态与证据区。
6. 每页三视口截图、同输入比较、P0→P1→P2 清零；随后专项、Web 累计、后端 GET、TypeScript、production build 与方案一致性复审。

## 结论

`final result: failed`

原因：新鲜基线已证明当前实现与 source visual truth 存在 P0/P1/P2 差异。该结论只冻结整改起点，不构成停工；下一串行任务立即进入 1:1 实现。

## Shell / Tab / 生意探究可信空整改复核

同一比较输入：

- source：`remediation-shell-tabs/source-inquiry-1280.jpg`
- implementation：`remediation-shell-tabs/current-inquiry-shell-tabs-1280.jpg`
- 两张图片均为本轮内置浏览器在同一 `1280×720` 视口的新鲜截图；截图前回读 implementation 已进入 `#analyst-tab-investigation` 且 `.business-investigation-empty-casebar` 存在。

已清零的基线差异：

1. P0 明暗体系：经营参谋 route-only Shell 已改为 source 的浅色 token；其他 AOS 路由不继承该作用域。
2. P0 首屏层级：页头 `48px`、上下文栏 `36px`、Tab `39px`，Tab 从 `y=84` 起，主区从 `y=123` 起。
3. P1 全局/二级导航：全局栏 `48px`，二级栏 `x=48, y=48, w=260, h=672`；活动经营参谋入口 `x=48, y=262, w=259, h=35.5`，与 source 一致。
4. P1 页头：标题 `x=64, y=4, 26px/39px, 700`；渠道控件从 `x=551.48` 起；“查看今日方案”按钮 `x=851.48, y=9.5, w=109.34, h=28`，并经浏览器点击验证可切换到真实“增长计划”Tab。
5. P1 Tab：容器 `x=308, y=84, w=972, h=39, padding=0 20px`；活动 Tab `padding=9px 14px, 12px/18px, 600`，与 source 一致。
6. P1 生意探究可信空骨架：Case 区 `x=328, y=137, w=926, h=127`；可信空边界 `y=274, h=32`；三阶段条 `y=316, h=54`；工作区 `y=380, w=926, h=160`。没有 canonical Case/Run 时不复制视觉稿演示数据、不把 unknown 显示为 0。
7. 功能守恒：侧栏路由、折叠按钮、专注模式、重新读取、键盘 Tab 与“查看今日方案”入口仍可用；真实业务写入、Provider、Source read、迁移和发布均未发生。

验证：

- 针对性：`EcommerceWorkshopShell`、`AppShell.workshop`、`BusinessInvestigationTab`、`AnalystPage` 合计 `33/33` GREEN。
- Web 累计：`255 files / 2300 tests` GREEN。
- TypeScript + production build：GREEN；仅保留既有 chunk size 警告。

仍需继续的差异：

1. 当前真实租户没有 canonical Case/Run，内容必须保持可信空，因此不能照抄 source 的演示 Case、商品数、步骤数或 checkpoint；后续只对组件几何、样式与状态语义做同构复刻。
2. 经营总览、驱动因素、问题诊断、增长计划、效果复盘、证据链、数据质量七页尚未逐页完成 1:1 对齐。
3. `1280×800 / 1440×900 / 1920×1080` 三视口与键盘/交互复核仍待逐页闭合。

`final result: failed`

原因：Shell、Tab 与生意探究可信空首屏已完成本段整改，但八菜单逐页与三视口总门尚未闭合；该状态继续进入下一串行任务，不构成停止条件。

## 七视图与三视口最终复核（2026-08-27）

### 同输入证据集

内置浏览器在 source 与 implementation 上分别进入同名菜单，并在同一轮比较输入中成对审阅；每档视口均保存八组 source/current 截图：

- `final-1280x800/source-*.jpg` 与 `final-1280x800/current-*.jpg`
- `final-1440x900/source-*.jpg` 与 `final-1440x900/current-*.jpg`
- `final-1920x1080/source-*.jpg` 与 `final-1920x1080/current-*.jpg`

八组菜单键固定为 `inquiry / overview / drivers / diagnosis / plan / effects / evidence / quality`。浏览器逐档回读 implementation 的 viewport/document 宽度分别为 `1280/1280`、`1440/1440`、`1920/1920`，页面级横向溢出均为 `0`；视觉验收结束后已撤销 viewport override。

### 逐页一致性结论

1. 生意探究：Case 条、可信空边界、三阶段轨道、工作区与右侧依赖门保持视觉稿的层级、尺寸比例与密集细边框；无 canonical Case/Run 时以同位可信空替代演示事实。
2. 经营总览：八节点经营节奏、经营摘要、待补证/待关注与三段协作链按视觉稿首屏比例落位；实际无 authority 时状态统一失败关闭。
3. 驱动因素：三列指标卡、下方贡献分布与事件流双栏保持视觉稿网格、卡片高度、字号层级和颜色语义；未把视觉稿曲线、金额、百分比复制为真实事实。
4. 问题诊断：四个二级 Tab、六行指标对比表与下方来源/异常双栏复刻视觉稿信息架构；无 exact metric 时使用“未知/blocked”，不显示伪百分比。
5. 增长计划：五阶段 lifecycle、左侧目标/行动/预算纵向主体与右侧审批/证据/Proposal 卡列保持视觉稿比例；无 approved exact revision 时不出现可执行写入口。
6. 效果复盘：有效、待补证、风险三段 Review 及下方四层经验/审批列保持视觉稿节奏与状态色；无归因 authority 时不自动晋升记忆。
7. 证据链：DecisionSummary、四个依赖节点、评价复核、Handoff 与阻塞明细保持视觉稿的 DAG 空间关系；未用 CSS 图形或伪连线冒充资产，节点引用仍由 exact ref 决定。
8. 数据质量：左上五轴增长护栏、右上先行指标、左下分母/新鲜度、右下异常阻断形成 2×2 主网格；`progress` 仅消费真实质量值，无 ref 时保持 blocked。

### 精确视觉与功能门

- P0：浅色 Shell、48/260/48 基础几何、标题、上下文栏、八菜单起点与主内容起点已清零。
- P1：三档视口的布局、组件层级、卡片比例、表格/轨道/双栏结构、边框、圆角、状态色和文字层级已清零；未发现裁切或横向溢出。
- P2：字体族沿用产品现有系统字体栈；字号、字重、行高、间距和密度按 source token 对齐。视觉稿演示数字、演示成功态和写按钮属于安全语义差异，不计视觉缺陷，且均在原组件位置使用可信 `unknown/blocked/read-only` 替代。
- 交互：八菜单点击与键盘切换可用；ArrowLeft 从“数据质量”切换到“证据链”已由内置浏览器复验。
- 专项前端：`29/29` GREEN；Workshop Web 累计 `255 files / 2301 tests` GREEN。
- TypeScript 与 production build：GREEN，仅保留既有 chunk-size warning。
- 后端 GET/canonical 专项：`28 passed`，仅保留既有 deprecation warning。
- 安全：没有真实 Source read、业务写入、Provider、迁移、外部副作用或发布；真实数据缺失不会被视觉稿演示值补齐。

## 最终结论

`final result: passed`

本结论仅关闭 BI-W11-02 的八菜单前端视觉、交互、对应只读后端合同与失败关闭硬门；不表示真实租户数据已就绪，也不表示 Adapter 安装、外部执行、迁移或发布 GREEN。
