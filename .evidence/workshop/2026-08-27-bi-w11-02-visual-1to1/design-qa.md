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
