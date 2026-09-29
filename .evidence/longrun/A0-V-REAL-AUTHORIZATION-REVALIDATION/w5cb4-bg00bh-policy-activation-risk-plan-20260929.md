# W5CB4 BG-00bh｜策略激活动作风险底线合同

## 上位方案与边界

231/231-9 要求策略正式批准与产品内恢复。BG-00bg 当前权威 PG 证实 policy/budget ActionType、Proposal、ApprovalEvent 均0；BG-00ba～bf 的五类新 active Store 门仍必须保持。现有 `classify_action_risk` 对未知动作默认 R1/draftOnly，不能让未来注册的策略激活动作隐式落低风险。本波只固定未来动作 ID 与服务器最低审批等级，不登记 `meta_action_type`、不产生 Proposal/Approval、不消费批准、不写当前库或开放 active。

## 文件级方案

- 新增 `services/aos-api/aos_api/aip_policy_activation_action.py`：固定五个不可拼接的 ActionType ID；Egress、Data、Network、Quota 为 R2，BudgetPolicy 为 R3。目标 hash、revision、租户、maker/checker、期限、撤销、一次性消费仍是后续独立合同，本文件不提供可执行授权。
- 修改 `services/aos-api/aos_api/aip_action_policy.py`：分类在通用文本关键字前识别上述固定 ID，R2 必须 maker-checker、至少1 checker、可走审批；R3 至少2 checker。客户端 hint 只能提高等级。
- 新增 `services/aos-api/tests/aip/test_aip_policy_activation_action.py`：先 RED 证明当前五 ID 被降成 R1/draftOnly；再 GREEN 覆盖五 ID、未知相似 ID 不匹配、hint 不降级和不误改既有动作。
- 专项与相邻风险分类回归、编译/diff 复审、verification、精确 m1 提交。该纯合同不等于正式 ActionType 注册或产品审批。任何涉及新 DB schema/当前卷迁移另立可恢复波。
