# W5CB4 BG-00bh｜策略激活动作风险底线验证

方案：`w5cb4-bg00bh-policy-activation-risk-plan-20260929.md`。本波只修改纯风险分类合同；未注册当前 ActionType、未产生或消费 Approval、未写当前 PG、未开放 active。

1. RED：新增专项测试后执行 `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_policy_activation_action.py -q --tb=short --disable-warnings`，6 failed / 1 passed；五个固定 ID 仍落 R1/draftOnly，证明缺口存在。
2. GREEN：`services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_policy_activation_action.py services/aos-api/tests/extension_runtime/test_cutover_action_policy.py services/aos-api/tests/aip/test_aip_provider_health_action.py -q --tb=short --disable-warnings` 退出 0，30 passed / 7 warnings。五个固定 ID 的 floor 为 R2（四类）或 R3（BudgetPolicy），maker/checker 与最低 checker 数随等级；相似未知 ID 仍 R1/draftOnly；客户端 R4 hint 只提高风险；相邻动作回归通过。
3. `services/aos-api/.venv/bin/python -m compileall -q services/aos-api/aos_api/aip_policy_activation_action.py services/aos-api/aos_api/aip_action_policy.py` 退出 0；`git diff --check -- services/aos-api/aos_api/aip_action_policy.py` 退出 0。复审实现与文件级方案一致：固定不可拼接 ID、风险 floor 在通用关键字之前，未加入 Store/HTTP/DB 激活路径。

风险与下波：这仍不是正式审批来源；当前 `meta_action_type`/Proposal/ApprovalEvent 均无策略激活项。BG-00bi 应设计精确目标绑定与批准消费合同（租户、policy type/id/revision/hash、maker/checker、期限/撤销、一次性 Receipt、同事务边界），先读现有 ActionApprovalEvent 与 Store，再选最小可测切片；不得据本波风险 floor 解除五类 active 禁入。当前 approved 安装 binding0、八候选0、Host/Owner/自然首链 pending。
