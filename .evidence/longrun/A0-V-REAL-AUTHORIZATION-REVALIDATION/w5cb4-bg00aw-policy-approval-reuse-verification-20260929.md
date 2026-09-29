# W5CB4 BG-00aw｜active 策略审批复用边界

方案：`w5cb4-bg00aw-policy-approval-reuse-plan-20260929.md`。只读复习 231-5、预算激活专属 Store/合同、ActionApprovalEvent 与网络/预算策略 Store；未写当前库或改准入。

- `aip_budget_activation_authority.require_exact_budget_activation_evidence` 的对象是 exact BudgetRevisionCreate、预览 hash、head version、maker/checker、过期/撤销/usageKnown；`aip_budget_activation_store` 以 tenant serializable 读取该专属 preview/decision/成员/撤销/ledger，但 `external_usage_proven=false`，消费在 `BUDGET_ACTIVATION_EXTERNAL_USAGE_PROOF_REQUIRED` 或 `...AUTHORITY_UNWIRED` 失败关闭。它不能替网络策略签发，也未使当前预算可 active。
- `aip_action_store` 的 ActionApprovalEvent 绑定 proposal_id/version/hash、action_binding_hash、approval_policy_hash、slot/eligibility；这是业务 Action 提案，不是网络/预算策略 revision 的当前批准。`aip_network_policy_contracts.py` 仅收非空 approval_ref，`aip_network_policy_store.py` 只核 active exact Egress 与网络范围，未见将该字符串解析为 maker/checker/对象 hash/撤销的当前审批读者。直接挪用 Action Event 或任意字符串会越权。
- 当前正租户 Egress/Network/BudgetRevision/BudgetPolicy 行均0、预算 preview/decision/receipt0、八候选0。正式 Owner/独立 checker 与外部用量完整性来源仍未具备。本波不通过手工策略写入改变它。

判定：网络策略 active 批准需要独立、可核的正式 authority 方案；预算激活已有专属机制但明确因外部费用证据缺失而关闭。下一波转 231 首链 C2b 受控联合证明：先只读审现有 Owner/fixture 是否能合法拼接，若能则 test-only RED/最小实现，不能则记录精确阻断并继续 BG-00 配置恢复代码。当前 Host/worker/Provider 和首链禁入。
