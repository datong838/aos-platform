# 客户工作台筛选遮挡与页签状态诊断

## Rules 与承接

使用AOS工程交付闭环、Product Design audit已捕获原图、CDP Bridge及231完整串行计划。Authority2039登记唯一写者codex-01a13484-f019-7d82-94ce-812396db9124，Task qyh-customer-visual-pointer-20261015至16UTC；旧38租约完全保留不重叠。原库只读/HostworkerProvider OFF/旧12与unknown不重放/disabled Schedule不启/商城源不读/noPush/用户dirty保护不变。原唯一真人授权、完整长期经营/安装/预算/八场景视觉/观察发布目标、每日及每次实际aos最新m1同原卷全面PGAPIWeb及aos2不重启全部保留。上一波保存closure已准确交付，不能重做558测试或SDK200当本波视觉通过。

## 已有现场与问题分级

maintenance-r11六张本轮1280x720/1440x900/1920x1080原稿/实际PNG逐组检视。filters都是32px且无横溢出，但正常指针被customer-tabs截获；三宽四filter中心elementFromPoint均命中tablist。源45-ecommerce-workshop.css:2820原客户视觉选择器position:absolute/z-index2/top0/padding52px覆盖筛选区；这是有DOM命中、真实超时及源码共同支持的缺陷。当前不能用force或DOMclick补过。

页签四次普通点击仍首tab；单独segment普通点击后等五秒selected未变；Enter能focus到segment但最终selected仍首项，disabled与inert/fieldset均已排除。原因尚未证明；可能输入适配/后台focus、事件或render状态问题，不凭推测改CustomerPage。后续一只读诊断调用出现Playwright page/context closed，必须先确认原9244准确owned target仍存活并重新连接同一目标，不能重启Chrome/新建其他标签/重新加载丢登录态/重放业务操作。没拿到正确活页不能推断产品错误。

## 原产品与视觉依据

228-客户关系工作台及05上级产品方案的任务驱动三栏、左任务与RFM/中计划进度结构化日志与Diff/右产物客户分层360仍是目标。原稿 /Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html/workshop-customer.html。只修正常pointer及键盘可用性，不填4207演示客户或67人任务，不把等待条件改成执行完成。导航密/等待横幅/六条件卡/真实计划日志产物缺口/宽屏留白/页脚同意规则语义继续单独登记。

## 文件级方案

首选唯一产品修改 /Users/ddt/work/projects/ai_agent/aos-platform/apps/web/src/styles/45-ecommerce-workshop.css：仅客户主视觉customer-tabs透明外容器pointer-events:none，实际button恢复pointer-events:auto。保留原position/grid/padding/尺寸/颜色/选中/焦点样式；不借提高全局z-index影响其他工作台。客户failure taskrail子button仍可用；透明padding应穿透到下层筛选。只有诊断证明CustomerPage状态逻辑有真实缺陷才修改已登记CustomerPage.tsx及CustomerPage.test.tsx，并先补方案/独立审查；不把transport故障补丁写进产品。其他文件扩围先登记Lease。

## 可执行步骤及门

1. 回读Authority/Task/HEAD/这三个文件无user dirty/实际Web89803冻源f036/API54057源0b0c888。回读旧writer边界，保留全部current调用与失败物证。
2. 新独立方案Prime PASS合法消费后才产品编码。RED用真实当前三宽hittest与普通pointer失败，保留原浏览器selector和命中几何，不能把JSDOM缺布局的测试当RED几何证明。
3. 先诊断页签：重新连接同一owned target，查看hasFocus/visibility；只在后台focus确有问题时可做临时focus emulation诊断并在finally清除。不改DOM/组件state，不调用隐藏React state，不借JS click制造交互通过。若仍无响应，检查原服务返回的四viewId与原onClick/onKeyDown绑定及组件load重置依赖，核事件是否实际到达，未知仅记录而不猜修。
4. 最小CSS二处声明后，仅冻结已提交base+本CSS overlay构建独立候选，不覆盖当前冻结生产源或用户dirty。适当运行现有客户组件/原视觉邻接测试、类型及构建，检查他台CSS和失败态/只读状态保持；这些不替代真实几何和交互。
5. 独立冻结代码质量复审及合法消费后精确m1提交。原Web维护Task新方案/完整manifest/实际旧Web PID+certain cwd+frontend source/bundle/API/PG guard、独立前效审查、一次意图仅Web切换（不替代daily全面重启），unknown只对账。
6. 同原唯一真人页面三宽真实normal pointer四filters各唯一aria-pressed、四tabs各唯一aria-selected与tabpanel对应、键盘Arrow/Home/End/Enter及焦点可见、elementFromPoint命中自身/子节点、32px/无横溢出及前后同CSS尺寸原稿图。不能用force或DOMclick补通过；所有正常readonly交互不得出现业务nonGET。原数据及API权限门、失败/unknown状态保持。
7. 独立现场复审，精确Delivery/m1/Authority/Prime七强，维护全部remaining继续；目标完整ACTIVE。若页签仍未解，不把filters修好算全交互/八台视觉完成，继续登记同Goal排障，不静默丢失该问题。

## 风险与回滚

pointer-events:none会影响容器非button交互，须核failure taskrail当前无其他需点元素，并在发现时只对实际交互子元素恢复，不能通配所有child又覆盖透明区。不同工作台共享样式不得扩散；所有修补加客户主视觉完整选择器。回滚仅撤销本CSS声明或本波已证明必要的客户组件变更，不改原数据/租户权限/运行准入。当前尚未写产品CSS或宣称修复。
