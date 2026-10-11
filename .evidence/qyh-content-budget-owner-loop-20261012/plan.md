# 栖月汇内容预算生产入口循环恢复方案

基线：m1 b8246b310f053a78b0374619aedc2c3fa1ee3929，AOS-001903。
复习231-5真实自动链和231-9原增长合同，复用原ContentBudgetCommandOwner、持久领取和Host提交，不建第二账本。

候选一：既有正式登录/独立发布配置接入，已获恢复授权，但配置来源信息待答。
候选二：原内容预算生产入口单项已知不确定性隔离，已登记本Task，独立于正式身份，无真实库写及Provider调用。
选择候选二。本次只改变循环调度，正式链仍不启动。

## 文件和最小行为

- services/aos-api/aos_api/ecommerce_content_budget_command_owner.py：run_once按reviewKey隔离ContentBudgetCommandConflict及TimeoutError，返回RECONCILE_REQUIRED；继续其他独立项。
- services/aos-api/tests/extension_runtime/test_content_budget_owner_loop.py：验证领取回读/提交回读不确定、超时、再次选择排除已领取、未分类异常传播和serve存活。
- 本目录：Task、RED/GREEN、方案复审、验证与Delivery引用。

原claim/execute_claim不变：attempt=1的持久领取仍不会进入pending选择器；不ack、不重新排队、不重发未知命令。claim前拒绝返回None仍跳过，不改变审批、预算、签名、租户或授权。
本次不吞并selector/Host-ready/程序错误；其他未分类异常仍传播。

## 验证和退出

先运行新测试得到RED，最小修复后专项及原预算/上游capacity/agentrun测试累计通过。循环无SQL变更，用原领取/提交不重发测试检查相邻约束；不以mock报告原生数据库或真实Provider通过。页面不改，无浏览器适用项。
复核源码和方案、自检精确diff，提交仅本Task文件，Delivery组件结论，CAS和7个强投影同步。代码不热切到现有服务；原647表/22个用户修改保持，正式全系统恢复仍未完成。
