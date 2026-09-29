# W5CB4 BG-00bk｜NetworkPolicy 正式入口只读审查方案

依 AGENTS.md、aos-engineering-delivery、231/231-5/231-9 与 BG-00bi/bj，先核正式 ActionType 注册、Proposal/Approval 产品入口、NetworkPolicy Store/HTTP 的最小接线点，避免把 hash 当授权。本波只读代码与历史当前事实，不动当前 PG/ActionType/active/Host。

阅读 `routers/actions.py`、`action_template_registry.py`、`aip_action_service.py`、`aip_action_store.py`、`routers/aip_actions.py`、`ecommerce_growth_cutover_proposal_gate.py`、`aip_network_policy_store.py`、`routers/aip_runtime_guard_policies.py` 与 Web ActionType/Draft/Runtime 页面。输出当前哪段可用、哪段缺失、优先代码切片以及迁移/浏览器门。验证以精确文件/行和只读检索退出码为准，文档落盘、m1 精确提交。
