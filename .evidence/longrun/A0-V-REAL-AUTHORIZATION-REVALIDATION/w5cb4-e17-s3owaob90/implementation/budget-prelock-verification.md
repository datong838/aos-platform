# 原Budget联合预锁提取验证

沿完整Task ACTIVE。原unique activation发现、原advisory、重核、Proposal/view/DevelopmentRisk块字节保持，提取native私有_prepare_formal_budget_approval；不取Owner/fence/head锁、不hold、不递增fence。原正式reader再核全部当前成员、内容、窗口与Receipt。方案见composition-plan.md。

首次写入脚本编码失败，budget-prelock-prehook-baseline.log为旧代码1passed/7.10s，不是RED。修正写入后budget-prelock-red.log缺私有入口ImportError，实际1failed，仅入口RED。最终budget-prelock-green.log：54passed/7warnings/53.02s，覆盖native正式预算13正负/并发/到期、原预算消费及精确角色/权限测试；正向同事务先prep再full reader，核原maker/checker和Proposal标识。所有测试terminal，精确diff检查通过。完整联合Owner/八facts/同caller三写/API/ToolBinding仍待，不能以两个预锁helper替代整个退出。当前142未写入，无UI改动浏览器不适用。
