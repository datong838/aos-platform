# 达人窄窗右栏裁切：同原稿对照与最小实施方案

## Rules 与完整目标

使用AOS工程交付闭环、Product Design audit/CDP Bridge、231完整串行计划及228达人邀约与签约驾驶舱。Authority2040，唯一写者codex-01a13484-f019-7d82-94ce-812396db9124，当前Task qyh-creator-visual-narrow-layout-20261015及maintenance-r13非重叠至16UTC；其他38租约不动。完整自然有来源经营首链/安装配置禁入恢复卸载重装/八真实场景全部视觉/持续观察发布目标不缩小，原唯一真人授权及fullC真预算最终人审边界保持。原DB只读/HostworkerProvider OFF/unknown旧12不重放/disabled Schedule不启/商城源不读/noPush/用户dirty保护；daily每次实际aos最新m1原卷全面PGAPIWeb与aos2不重启不变。

## 已核实的当前事实

当前m1 HEAD90a440c1ae825d6d220c35a001399530666b3ba5，实际Web61045/8dbb764源、API54057/0b0c888 backend与当前一致、原PG同权威卷/Started20:36:36/schema161/650/绑定0。上一波客户两处pointer修复已交付并保留，不重新跑407/SDK代替本波证据。当前CSS及CreatorGrowthPage/test无用户dirty，本波尚未改任何产品文件。

原owned target通过原真人正常登录/me核身份org-org/dev-project/subject6f31...c657。首次侧栏普通指针导航未确认URL变化，回读仍客户页，保存失败；随后沿可见链接exact href一次GET，正常表单登录200，首次board可见等待超时，后续fresh DOM明确板面为visible grid、根及四辅助GET200，无业务nonGET。原稿首次goto观察超时后回读URL已到creator，未重复导航。所有失败/等待观察保留，不能把尝试当成功。

真实三宽截图及原workshop-creator-outreach.html同CSS截图共六图已逐组检视。1280时board client972/scroll1100，CSS列260+520+320，右边界1408，overflow:hidden把右128px裁掉；1440为260+552+320、右界1440，1920为260+1032+320、右界1920，均不出现此项裁切。document宽度不溢出不能作为内容未裁切的证明。1180既有media断点另证实client872/scroll970、列225+460+285、右界1278，裁98px；因此不能只修base而留下断点min460。首次采样遇CDP句柄关闭及页面重新出现登录门，已只读核同一原target、正常表单恢复后取到当前证据，未重启Chrome。原稿在1280仍可看完整右栏，中央宽表允许内部滚动而非裁右栏。

## 产品方案军规

达人库、招募、商务签约、履约、长期关系五阶段均保留。默认Draft-only，拒绝/退订服务端阻断复邀、平台接受不等于SIGNED合同、PRELIMINARY不晋升长期核心达人；不抓私有联系方式，不放开邀约发送/合同/履约/审批预算或回执门。当前实际是无正式达人空态，原稿147达人/GMV/匹配分等演示不填实际。原产品中栏flex自适应，与固定520下限冲突；修补应允许中栏在可用宽度内收缩而非隐藏右栏/缩放全页/移除导航或业务条件。

## 文件级实施

首选唯一产品修改 /Users/ddt/work/projects/ai_agent/aos-platform/apps/web/src/styles/45-ecommerce-workshop.css：客户主视觉pointer规则不动；仅creator主视觉.creator-growth-board的base minmax(520px,1fr)改minmax(0,1fr)，以及既有max-width1180断点minmax(460px,1fr)同样改0。保留base左右260/320、断点225/285、现有高度/内部overflow/字号/色彩。三子区已有min-width:0/overflow:auto，允许中间必要内部滚动；右侧说明与控件要完整可见。

仅在实际子区overflow证据证明上述不足时才补最小creator选择器，并先追加方案/独立审查；不猜改组件逻辑。CreatorGrowthPage.tsx及.test.tsx已登记供必要诊断/回归，默认不修改。其他额外共享文件/测试先扩Task Lease。

## 验证与交付门

1. 独立方案Prime PASS合法消费后才开码。当前真实1280几何/原图已为RED；1180既有断点另取邻接反例，不用JSDOM无布局测试伪装。
2. 最小CSS改动后冻结最新Git archive+唯一CSS overlay，不复制用户dirty/.env；运行现有工作台/API组件累计、类型检查和生产构建，保留前后SHA。核客户两pointer声明和他台规则不变。
3. 若需非空长表/长文本几何，应用明确隔离的原组件fixture，禁止调用原API/执行Actions，不把fixture当真实身份经营证据；额外文件先登记。真实当前页面本波空态先验。
4. 冻结独立代码质量PASS合法消费后精确提交。maintenance-r13新鲜最新commit Web764完整Git/disk manifest、原PG/API/旧Web61045准确PID/source/entry/租约/head/原650before、独立前效控制器门和一次Web意图更新，unknown只对账，不signal原PG/API/Chrome；不替代daily全面重启。
5. 同原真人实际1280/1440/1920及1180边界：board三子区right全部不超board/viewport、board scrollWidth不因列最小宽度超client、右栏关键controls可见且普通中心hittest可达、内部滚动可到末尾；核五tabs/搜索筛选只读状态和正常键盘焦点（不点击会产生业务POST的按钮），current empty/blocked文案保留；header/metrics长文不得覆盖相邻格。普通native输入明确buttons1/0并回读状态，不能force/DOMclick。
6. 同CSS尺寸actual/reference当前截图逐图对照；保留原稿非空与实际空态差异，不称像素全一致/五阶段全经营/a11y完成。必要时正常登录恢复已知expired JWT，不读/导出会话密钥，不重放未知动作。
7. 当前me/正式只读SDK/匿名与scope deny/businessNonGET[]、fresh650after全表行数hash与before相等及实际版本/卷/端口核验；现场独立Prime→精确Delivery/m1/Authority/Prime七强及下一已登记波。

## 风险与未完成

中栏可收缩后，五项指标、长单词或内表可能产生内部滚动；应明确验证可达性和换行，不用隐藏内容消掉overflow。只承诺本断点裁切切片，手机/任意极窄窗口、非空五阶段、其他台原视觉差距/辅助失败假0/客户任务日志产物与页脚语义、完整经营/预算人审/安装/观察发布全部继续。回滚仅本creator CSS两处值，不改原数据、API、权限、发送或客户已交付pointer。
