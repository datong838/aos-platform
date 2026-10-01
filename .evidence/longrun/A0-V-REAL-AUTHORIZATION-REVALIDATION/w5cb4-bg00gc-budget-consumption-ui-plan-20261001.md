# BG00GC 已批准预算启用 UI 与原请求恢复计划

基线AOS-001043/b8d1dc01，7强一致CURRENT。复习231-5审批精确引用、unknown只对账、费用风险与435/436；BG00GB产品消费API作为唯一入口。预算配置启用不是手工业务Run，不启动Provider/Host/worker，不读商城源。

## 文件级最小实现
- apps/web/src/api/aipBudgetCost.ts：在现有CostRef增加consume操作，映射consumption-request；body只proposalHash/decisionId；严格Receipt完整字段/proposal引用/预算版本hash/批准关联校验，历史Receipt不宣传当前运行授权。继续apiPostUnqueued，无队列/自动重发；URL只保存ref/operation/attempted，不保存凭证/批准正文。
- apps/web/src/pages/s2/BudgetCostReviewPanel.tsx：复用既有guard/run/load/恢复状态机，consume仅原maker、当前来源同身份、approved未撤销未过期、not_attempted且未attempted、明确选择时可提交。第一次点击前保存attempted；刷新只查询，unknown不能恢复提交按钮。现有decide/revoke行为不变。
- apps/web/src/pages/s2/BudgetCostReviewPanel.test.tsx：RED锁消费请求精确body/路径、重复及unknown不重发、consume URL刷新只GET、非maker/撤销/过期拒绝、身份切换丢弃迟到响应、错误Receipt拒绝；保留旧审核测试。

## 验证与边界
专项→相邻预算UI累计→类型检查/适用browser-pilot只读页面验收→复审verification→精确提交/Delivery/CAS/437/D-waves。前端fixture仅交互逻辑证明，不代表正式批准/预算启用或业务首链。当前正式库只读不迁移/不重启，正式不同UID消费配置仍独立验收。UI不得显示首链完成或主动启动服务。
下一BG00GD继续合法development价格/政策producer与当前部署配置缺口核验；正式最新版本重启仍需独立安全恢复波。
