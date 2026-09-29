# W5CB4 BG-00bg｜正式策略激活审批来源审查

方案：`w5cb4-bg00bg-formal-policy-approval-source-plan-20260929.md`。本波只读代码/当前 PG；没有策略发布、迁移、Host/worker/Provider 或商城源访问。

1. 当前权威卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927` 只读事务查询（`docker --context colima-aos-extension exec aos-a0v-recovery-pg psql ... -XAtc 'BEGIN READ ONLY; ... ROLLBACK;'`）退出 0：`meta_action_type` 中 policy/budget 动作 0；`org-org/dev-project` 策略 ActionProposal 0、ActionApprovalEvent 0、BudgetActivationPreview 0、Decision 0。
2. `aip_action_store.py::action_type_snapshot` 从 `meta_action_type` 取当前动作；没有注册动作就不能由当前产品创建正式策略 Proposal。`aip_action_policy.py` 只对列明的控制动作设 R2 floor，新的策略动作若未经冻结将落通用分类，不能据此假设 maker/checker 强度。
3. `aip3_001_action_control.py` 的 ActionApprovalEvent 强绑定 `proposal_id/version/hash`；已有 Schedule 等使用方还对 action type、target/binding hash、审批窗口逐项复核，不能把其他 Proposal 的事件 ID 当策略审批。
4. `a0v_110_budget_activation_preview_approval.py` 的 preview/decision 明确绑定 `budget_id`、目标 hash、maker/checker 与期限；`aip_budget_activation_store.py` 消费仍因外部用量证据未接线失败封闭。不能把它复用作 Network/Egress/Data/Quota/BudgetPolicy 的通用审批。

判定：正式策略激活的当前来源/产品入口均不存在。BG-00ba～bf 的五类新 active 禁入是必要安全门，但不是配置完成。下一波 BG-00bh 先写固定策略激活目标与审批来源的文件级合同：ActionType/risk floor、精确 target hash/revision、maker/checker、撤销/期限、一次性消费 Receipt、同事务 Store 边界及产品预览。方案审查后只选一个可独立验证的代码切片；任何新迁移在 test-only 克隆验证，当前库迁移另立备份/克隆/零执行波。当前 approved 安装 binding0、八候选0、Host/Owner/自然首链 pending。
