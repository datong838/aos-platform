# W5CB4 E17-d｜BG-00 预算 active 生产者只读审计与下一切片方案（2026-09-28）

## 上位合同

- 231-9 §BG-00 要求失效原因、正式更新、影响预览、恢复进入产品入口；231-3 的安装消费必须同事务复核当前四源，不允许页面入口或字符串批准冒充权威。
- 本波承接 E17-c 已接通的预算 **draft** 入口。当前八类 active 候选为 0，当前权威库只读，正式 Owner/批准身份未提供；不构造金额、Owner 或批准引用。

## 文件级只读定位

1. `aip_budget_contracts.py:21-35`：`BudgetRevisionCreate` 有 Owner/overBudgetApprover 和 lifecycle，却没有批准引用或可核验的批准对象。
2. `routers/aip_budgets.py:61-76`：POST 仅要求登录主体、幂等键、If-Match，直接把包括 active 的请求交给 `AipBudgetAuthorityStore.publish`。
3. `aip_budget_store.py:78-155`：CAS、修订、Receipt、租户作用域具备；未见 active 之前读取独立批准权威或核对 maker/checker/金额/期限的步骤。
4. `aip_model_governance_policy_contracts.py:24-48,73-109`：预算策略 `approvalRef` 是非空字符串；可选开发费用授权只核对两处字符串相等和窗口，不能单独证明批准事件真实存在。
5. `aip_model_governance_policy_store.py:175-191`：预算策略发布先核已 active 的精确预算修订，再 CAS 写策略；此处未见独立批准事件读回。
6. 既有 `test_aip_budget_api.py`、`test_aip_budget_store.py`、`test_aip_model_governance_policy_store.py` 用测试主体、示例预算和 `approval:test` 发布 active。它们证明接口/存储机制可工作，不是当前正式批准证据。

## 结论与下个最小编码切片

当前预算 **draft** 可以由产品入口创建；active 路径缺正式批准核验。不能通过填写 `approvalRef` 或把 draft 改成 active 来凑齐八类候选。下一编码切片先确认复用哪个现有 Approval Owner/精确版本/Receipt，而不是新增第二套审批表；核验合同必须绑定租户、预算 ID+revision+hash、金额/窗口、maker/checker、批准状态和到期/撤销，并在 active 写事务内读回。若找不到合法 Owner，则只加 fail-closed 正式入口和阻断信息，不创建 active。

预定文件级变更：`services/aos-api/aos_api/aip_budget_contracts.py`、`aip_budget_store.py`、`routers/aip_budgets.py` 与三者专项测试；如需要 UI，延伸 `apps/web/src/pages/s2/BudgetRevisionSetupPanel.tsx` 及测试。编码前补具体 Approval Owner 方案与接口，先 RED，再最小实现、隔离 PG/相关累计/类型构建；当前真实库仍只读。不得影响既有 draft、CAS、幂等 Receipt、租户隔离及旧修订读回。

本波本身只读定位，不改上述代码；任务验收为精确指出缺口、保留禁入并给出下一文件级门。浏览器截图仍待 `browser-pilot`。
