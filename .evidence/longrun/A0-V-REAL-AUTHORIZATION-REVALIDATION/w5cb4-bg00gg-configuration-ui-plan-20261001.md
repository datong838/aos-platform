# BG00GG 费用配置UI与恢复方案

基线AOS-001047/e5405ddb；复习231-5费用承担与恢复军规、440和现有aipBudgetCost/BudgetCostReviewPanel/useBudgetRequestGuard。复用已有面板与身份epoch/attempt守卫。

## 文件级方案
- apps/web/src/api/aipBudgetCost.ts：CostRef新增configure，映射configuration-request；消费返回保留精确BudgetRevision引用；配置返回严格三类引用/receipt/proposal/hash/decision、price/policy固定ID后缀和revision1。已知source或consumed时必须交叉核验。submit configure必须先有已观察的消费Receipt及批准来源；POST unqueued，URL只存id/operation/attempted。
- apps/web/src/pages/s2/BudgetCostReviewPanel.tsx：增加“生成费用配置”操作与明确确认；load先读来源、消费原请求再读配置原请求，当前maker/approved未撤销未过期、已观察消费与配置not_attempted且无attempt才可点。恢复仅GET，无自动提交。source/consumption随身份或输入改变一起失效；展示历史配置引用，不显示业务已启用。
- apps/web/src/pages/s2/BudgetCostReviewPanel.test.tsx：RED缺操作→完整实现，涵盖消费缺失/漂移/身份变更/unknown/恢复不重发、错误引用拒绝、正常精确提交和历史文案。

## 验收与边界
Vitest为前端合同/交互替身证据，不当正式业务；专项/三个预算面板累计/tsc，browser-pilot独立浏览器只验当前页面无合法来源时禁入，留截图；不填假账号、不提交真实业务。正式授权路径仍待真实凭证/不同UID/当前实例恢复波，不开启Provider/Host/worker，不读商城源/旧12Run/手工Run/230L0。服务端GE/GF仍是最终权威，UI仅前置引导。Watchdog方案不在本波实施。
verification/精确提交/Delivery/CAS/7强一致/441与D-waves。下一BG00GH核Model/Task联合路径，不能把页面或测试当首链完成。
