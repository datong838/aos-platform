# 价格观察筛选行视觉修复方案

Rules：用户AGENTS、231串行完整Goal、AOS工程交付闭环及原视觉稿同尺寸对照。当前Authority2033/headc186，独立同owner CSS Task已登记且不重叠；处置GET审计及完整maintenance-r6保留。原真人授权/原数据/日更与每次aos完整PG→API→Web/独立Prime/完整经营目标不变。

## 已有实际 RED 事实

原正常登录、最新API246/Web1627当前价格空/待条件页，1280×720/1440×900/1920×1080与foundry/html/workshop-price-governance.html原稿各三图已同尺寸检视。实际四滤钮高89/255/345px；1440/1920明显呈长竖胶囊，1280已排除换行。证据maintenance-r5/price-menu-deny-visual-r1.json及六PNG/sha。原稿的47SKU/价格/异常属演示，不是待恢复的真实经营数据。

源码：45-ecommerce-workshop.css中price primary selector把.price-observations放进固定可用高度主区；该section自身display:grid，implicit auto rows在剩余高度里stretch，第一nav track连带flex children被拉高。不是按钮文字/业务状态/原数据所致。需先用隔离浏览器原CSS与原组件的空态场景复现此高度失败，不能靠样式字符串断言当视觉证明；若未复现则先修正fixture事实而非改产品。

## 精确文件与最小候选

只改apps/web/src/styles/45-ecommerce-workshop.css，在现有.p-app.is-workshop-primary-visual .ecommerce-workshop-shell[data-module-id="ecommerce.price-governance"] .price-observations规则加align-content:start，使原nav和后续条目按内容高度排布，剩余留白留在列底部。预计一个声明，不改其他selector、全局grid/flex、颜色、字体或三列尺寸；不硬编码89/255/345窗口值，不设置按钮固定大高度遮掩父布局。

Task不含React/API/锁文件；不改筛选click/aria-pressed/顺序、按钮禁用或权限、unknown/empty/blocked/Receipt语义，不覆盖已登记的Page辅助失败假0缺口。不借视觉修复宣称价格处置/自然经营可用。若这一声明不能消除问题，先补充方案再扩候选，不隐性改组件或其他八台布局。

## 验收与交付顺序

独立Prime方案合法消费 → 隔离冻结原CSS+原PriceGovernancePage相同shell/视口空态重现RED（按钮>48px） → 最小CSS → 空态及非空合法组件fixture在1280/1440/1920截图及几何：四按钮同单行内高度一致且不超48px、内容不重叠或截断、筛选无匹配空态正确、aria-pressed及筛选原交互有效、无意外横溢出。1280允许正常紧凑换行，不将桌面强压单行作为唯一合格标准。

隔离fixture是只读验证，使用明确synthetic tenant/data且不连接真实API；不生成任何Run/业务写，不把fixture截图当原客户经营。正常legacy/非primary与其他七台共享样式不变，以selector作用域及相邻组件回归验证，不复制产品实现写样式快照测试。

fixture代码只在本E：从当前已提交Web及必需packages冻结，排除.env/userdirty；挂载未改的PriceGovernancePage、相同p-app.is-workshop-primary-visual与scoped shell、原样式入口。client prop提供现有强类型测试夹具形状的empty及非空只读观察；所有AIP动作adapter均明确throw禁止执行。专用本地端口先查空、owner意图与实际PID对账；浏览器阻断非该fixture本地来源请求，不走原登录/API/Provider。对照原CSS与一声明候选CSS，只测几何和原筛选交互；不得用fixture保存/审批/运行任何真实业务。

冻结候选排除userdirty，相关Workshop回归/TypeScript或构建按适用范围验证，独立代码质量Prime合法消费后精确提交。fresh Web冻结/维护控制器质量门后仅更新Web，API/PG不signal；原真人同页面、三宽度原稿复拍、核心只读筛选和原650不变及独立livePrime后准确Delivery/AuthorityPrime。每日/每次aos完整最新同卷full restart独立保留；aos2不重启。

完整231Goal、fullC唯一真人最终预算/原部署/自然CaseRun建议exact评审内容受约束能力产物人审续跑总控Wiki、安装全生命周期/八场景/全视觉/连续观察发布全部继续。HostworkerProviderOFF/业务DBREADONLY/unknown旧12不重放/disabledSchedule/source/noPush禁界不变。
