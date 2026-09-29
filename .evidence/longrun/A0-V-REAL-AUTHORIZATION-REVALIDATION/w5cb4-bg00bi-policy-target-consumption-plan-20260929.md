# W5CB4 BG-00bi｜策略激活目标与批准消费只读审查方案

规则：AGENTS.md、aos-engineering-delivery、231/231-5/231-9 与当前 E17 五类 active 禁入。目标是从现有正式 ActionApprovalEvent/预算激活预览和策略 Store 中定位可复用的精确绑定与事务边界；本波不改代码、不写当前 PG、不注册动作或开放 active。

文件级阅读：`aip_action_store.py`、`aip_action_execution.py`、`aip_budget_activation_store.py`、`aip_network_policy_store.py`、`ecommerce_growth_cutover.py`、`aip3_001_action_control.py`；对照 231 中 exact tenant/revision/hash、maker/checker、撤销/期限、Receipt-first/reconcile 和自然链要求。判据：区分风险 floor、审批事件、目标绑定和一次性消费四层，指出缺口及下一波最小实现点。输出 verification、D-waves、上下文、精确 m1 文档提交。
