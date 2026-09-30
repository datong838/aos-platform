# BG00FO 预算review产品接线方案

基线AOS-001029 / m1@2d035691；Task W5CB4-BG00FO-20261001。复习231主计划/231-5§5/6/7，八工作台公共产品契约§3/4/8/11、422、BG00FL/FM/FN及CapacityPage预算入口。

## 目标与最小补齐
原预算页只有draft；FN后端可持久preview/decision/revoke请求。新增同页审批区，准备预览、独立复核、撤销批准三个操作；均先读来源/原请求再允许提交。当前budget GET无headVersion，避免让用户手填或把revision猜成headVersion；撤销前也必须看真实批准来源。

## 文件级计划
1. Store新增get_candidate：当前原actor OIDC/member、READ ONLY/repeatable read/aos_runtime双scope；同snapshot JOIN head+revision，检查payload/contentHash/tenant/ID/revision/lifecycle=draft，返回currentRevision/headVersion/target（仅下一版active候选）/activationEligible=false。不执行账本消费或激活；正式preview仍原Store完整复验。
2. Store新增get_decision_review：只读原decision+preview+revocation，当前maker/checker/member、同scope及preview/target/hash核验；返回历史decision/preview/revoked，不能当执行授权。契约DTO与GET /activation-candidates/{budget_id}、/activation-decisions/{decision_id}，no-store，异常503非不存在。
3. 新api/aipBudgetActivation.ts：严格解析有限状态、候选/预览/历史决定，复用apiGetAuthoritative/apiPostUnqueued，不使用离线队列。恢复URL仅operation/resource/revision/head，目标金额/原因/token不入URL。
4. 新BudgetActivationReviewPanel：按三操作读取权威内容，展示金额/期间/负责人/独立审核人/过期撤销信息；checker必须用户输入，审批选择无默认通过，撤销须原因。当前身份epoch、ref指纹与同步busyRef隔离迟到响应/双击；URL恢复仅只读查询，不自动提交。已尝试或unknown/冲突/错误不能重新提交，即使后续not_attempted也保持冻结；查询仍可用。查看历史成功不表示生效或可执行。
5. CapacityPage仅import+挂载新面板，原draft功能保持。不自动读取商城、不启Provider，不添加激活按钮。
6. tests：新增真实隔离PG/TLS-JWT HTTP候选和历史来源/租户/成员/无写；前端DOM交互覆盖先读后提交、双击、unknown、编辑源/身份变化、刷新安全引用恢复、响应格式拒绝及三操作。单元stub仅UI合同，非业务通过。运行相邻预算后端、前端专项/累计与tsc；browser-pilot实际页面只读/禁入验收，截图留证，正式身份缺失时不能用假账号代替。

## 风险与收口
当前正式库只读；代码123>旧实测live118，禁止本波隐式升级/全栈切换。页面看到不等于后台最新或首链成功。两新增read只读，无migration。正式目录/外部身份未部署时503为真实禁入。原draft刷新持久恢复仍后置待办，不冒充修复。外部usage/原子激活/自然首链仍pending。
RED→实现→专项/相邻累计→适用浏览器→复审→verification→m1精确提交/Delivery/CAS/423/D-waves/Prime。下一波BG00FP核对预算外部usage权威最小缺口及合法来源，推进首链必要配置；未知请求无副作用裁决与draft恢复登记后续。

复审补充：原GET /activation-previews/{id}也显式no-store（只补响应头，原读取权限和内容不变）；身份切换后异步来源返回立即截断，不能再更新URL或继续查询旧引用。相应HTTP/DOM负例覆盖。
