# O1-UX4 统一知识图谱画布设计 QA

## 对照证据

- source visual truth：
  - `/var/folders/xw/rbrhth3s0jj8pygcx6knfs8c0000gn/T/codex-clipboard-50ff0523-06ea-49f2-9e17-0c175e72e3f9.png`（Foundry Object Explorer，2048×1154）
  - `/var/folders/xw/rbrhth3s0jj8pygcx6knfs8c0000gn/T/codex-clipboard-d55d183f-774f-4409-a597-c663ca3cdb67.png`（Foundry Graph Health，2288×1220）
  - `/var/folders/xw/rbrhth3s0jj8pygcx6knfs8c0000gn/T/codex-clipboard-b9d28ed6-05a8-423f-a23c-38594377ff05.png`（关系图谱表现参考）
- implementation screenshot：`.evidence/o1-ux4-object-graph.png`（498×584，CSS viewport 498×584，deviceScaleFactor 1）
- normalized comparison：`.evidence/o1-ux4-design-comparison.png`（1734×760；保持完整画面比例并按等高缩放）
- route/state：`/workshop/graph?type=Payment&id=niushop:1:12`，`org-org/dev-project`，Graph 模式，2 hops，`Order.hasPayment` 过滤。

参考稿为桌面宽屏，Codex 内置浏览器当前为 498px 响应式窄屏，不能把二者当作逐像素同视口复刻；本次比较的是已冻结的产品结构、信息层级、画布能力和窄屏降级。窄屏默认邻居列表、显式进入全屏图谱是 UX4 方案要求，不是视觉漂移。

## Full-view comparison evidence

- 主图从旧 420px 绝对定位块升级为占满可用区域的独立画布；详情仍为按需抽屉，进入全屏后主图覆盖工作区。
- 参考稿的图工具、图例、节点卡、方向边、类型色板和大面积画布均有对应实现。
- 窄屏下查询条件会换行，工具栏保持可点，图例横向滚动，默认列表避免不可读的微缩图；用户显式选择“图谱画布”后可平移和缩放。

## Focused region comparison evidence

- 工具栏：放大、缩小、重置、适配、放射/分层、邻居列表/图谱、可见路径均已浏览器点击验证，不是静态按钮。
- 图主体：Payment `niushop:1:12` 的真实快照在 2 hops 下显示 9 节点/8 边；`Order.hasPayment` 过滤后为 3 节点/2 边，水位保持服务端值。
- 节点：类型稳定配色、标签、规范 ID、depth、选择/邻居降噪、Enter/双击重新取 seed 均有实现。
- 全屏：按钮进入固定全视口画布，退出按钮和 Escape 可恢复页面。

## Required fidelity surfaces

- Fonts and typography：沿用 AOS 既有字体和文本 token；标题、元数据、边标签三层字级清楚。窄屏 watermark 自动换行，无重叠。
- Spacing and layout rhythm：主图区不再被详情挤成窄纵栏；工具栏和图例分层，画布保留最小可操作高度；390/498px 使用列表优先。
- Colors and visual tokens：全部复用 `--aos-*` token；Object Type 使用稳定离散色板，选择态使用现有 accent。
- Image quality and asset fidelity：页面无需要生成的位图资产；知识图谱 SVG 是数据可视化渲染，不以装饰性自绘资产代替参考素材。
- Copy and content：全部说明真实 authority、watermark、节点/边数量和截断状态，不使用模拟业务文案。
- Accessibility：工具栏为语义 toolbar；节点可聚焦并支持 Enter/Space；所有查询控件有 label；移动端列表保留相同 selection。

## Comparison history

### Iteration 1

- [P1] 旧图谱被压在 420px、仅六个绝对定位节点，不能表达真实 GraphSnapshot。
- [P1] 展开、缩放、布局和过滤缺失或无实际动作。
- [P2] 390px 直接画图会导致节点不可读。

修复：抽离 `OntologyGraphCanvas`；实现确定性放射/分层布局、pan/zoom/fit/reset、全屏、节点与边、查询过滤；390px 默认邻居列表。

### Iteration 2

- 浏览器后证据：真实 Payment 快照、1/2 hops、关系/对象类型过滤、可见路径、布局切换、缩放、适配、节点选择和全屏均通过；Graph Health 复用统一画布，Domain 成功读取，当前无运行血缘数据时明确失败关闭；控制台错误 0。
- 未发现仍需修复的 P0/P1/P2。

## Findings

- 无未解决的 P0/P1/P2。

## Follow-up polish

- [P3] 在可获得 1440×900 的内置浏览器视口时补一张同宽桌面截图，作为更精确的像素级密度对照；不阻断本波功能与响应式验收。

## final result

passed
