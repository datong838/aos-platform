# W5CB4 BG-00bg｜正式策略激活审批来源审查

依 231/231-9、BG-00aw 和 BG-00ba～bf 的安全禁入，先读现有 ActionProposal/ApprovalEvent、BudgetActivation preview/decision、当前 ActionType 注册和当前租户只读记录。目标是找到能同时绑定 policy kind、目标 revision/hash、maker/checker、期限/撤销、一次性消费与产品入口的正式来源；不能把 ActionApprovalEvent、历史批准字符串或 BudgetActivationDecision 跨目标复用。当前库只读、Host/worker/Provider 关闭。

文件级：`aip_action_store.py`/`aip_action_policy.py`、`aip3_001_action_control.py`、`a0v_110_budget_activation_preview_approval.py`、`aip_budget_activation_store.py`、五类策略 Store/Router。只读查 `meta_action_type` 当前 policy/budget 动作与 `aip_action_proposal`/`aip_action_approval_event` 当前数量。合法来源缺席时不写伪正向；输出精确缺口和下波独立可实施项，按迁移单独门管理任何 DB schema。
