# W5CB4 BG-00av｜网络/预算策略正式提交权威审计

方案：`w5cb4-bg00av-policy-submission-authority-audit-plan-20260929.md`。本波只读，未创建任何策略、批准、配置或运行资源。

1. 网络策略合同 `NetworkPolicyRevisionCreate` 限 https/443、精确公共 DNS、owner/approvalRef 非空、有效期；`AipNetworkPolicyStore.publish` 要当前 active exact EgressPolicy，并核 host/scheme/port/window 子集，即使提交 draft 也执行。`require_exact_active` 拒 draft。API 用 Idempotency-Key/If-Match；代码只验证 `approval_ref` 非空，未发现网络策略专属当前 maker/checker、撤销或决定消费。该字符串不能当正式批准。现有 `/aip/model-runtime` 只有出站策略草稿准备，没有网络策略发布表单。
2. 预算策略合同要求 exact BudgetRevision，Store `publish_budget` 即使 draft 也要求该 BudgetRevision 为 active、窗口/币种/硬停匹配；`require_exact_active` 额外对 development cost authorization 做 current head/model 范围核。API 用 Idempotency-Key/If-Match，但通用 `approval_ref` 不是预算激活批准的同事务消费。预算 Revision 的正式 active 仍被 422 阻断，E17-y2 预算预览 `activationEligible=false`；`/aip/capacity` 有草稿预算准备，但无合法 active 预算或预算策略表单。
3. 当前 `aos_current_preview_20260927@a0v_114` READ ONLY SQL：正租户 Egress/Network/BudgetRevision/BudgetPolicy 四类所有 lifecycle 分组均 `[]`，预算 activation preview/decision/receipt 各0；八类当前候选0、运行绑定0、Host禁入。没有合法当前前置可提交上述两项。BG-00au 链接是准备入口，不是直接创建策略或准入。

判定：当前实例缺 Owner/独立 checker、正式费用上界和有效前置，不能手填 approvalRef/测试身份或放开 active。下一波 BG-00aw 返回首链必要集的独立机制：对现有网络/预算策略 API 的 active 准入合同做方案/RED 审查，优先找可复用当前 Approval authority；如需新 authority/migration，先封存文件级设计，转不依赖该实例的配置恢复产品项。未完成首链、浏览器截图、持续观察/发布决定。
