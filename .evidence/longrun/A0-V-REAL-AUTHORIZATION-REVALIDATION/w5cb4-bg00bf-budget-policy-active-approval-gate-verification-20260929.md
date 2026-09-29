# W5CB4 BG-00bf｜BudgetPolicy 新 active 审批禁入验证

方案：`w5cb4-bg00bf-budget-policy-active-approval-gate-plan-20260929.md`。隔离临时 PG 中已具备 test-only active BudgetRevision 的前提下，RED 证明仅 `approval:test` 的新 active BudgetPolicy 原会被受理，退出 1，`Failed: DID NOT RAISE BudgetPolicyApprovalRequired`。这不是正式 BudgetRevision 激活证据。

最小修复：`AipModelGovernancePolicyStore._publish` 同请求 Receipt 幂等回读后、BudgetRevision 依赖检查和新 Revision/Receipt 写入前拒绝 BudgetPolicy active，错误码 `AIP_BUDGET_POLICY_ACTIVE_APPROVAL_REQUIRED`；HTTP 返回 422 中文提示。拒绝后同 policy ID 不存在。草稿仍执行精确 active BudgetRevision 依赖校验；旧 active BudgetPolicy 读取在隔离 PG 以既存行核验，Quota 已有门不变。

| 命令 | 结果 |
| --- | --- |
| `python -m pytest test_aip_model_governance_policy_store.py test_aip_model_governance_policy_api.py test_aip7_model_runtime_store.py -q --tb=short --disable-warnings` | 退出 0，13 passed。 |
| 两生产文件 `compileall -q`、精确五文件 `git diff --check` | 退出 0。 |

当前权威库只读，无 schema/Host/worker/Provider 变更。正式 maker/checker 与预算外部用量权威均未接通；DB 直写门、当前八候选/Owner/自然首链待证。测试夹具既存 active BudgetRevision/Policy 不是当前业务完成。browser-pilot 无可调用工具，本波无截图验收。

下一波 BG-00bg：从既有审批/预算证据中审正式策略激活来源，确定最小同事务 maker/checker/撤销/期限/消费合同和产品入口；有独立可实现代码项才 RED，不能用字符串/环境捷径开启 active。
