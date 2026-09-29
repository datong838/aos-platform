# W5CB4 BG-00bi｜策略激活目标与批准消费只读结论

1. 上位方案 `231-9` §2/§4 要求跨层 exact tenant/resourceType/id/revision/hash 与当前安装代次；`231-5` §5 要求批准绑定输入/预览/产物、能力/动作/预算/到期，执行前重验撤销和版本，重复事件只产生一次动作。BG-00bh 的 R2/R3 floor 仅是强度分类。
2. `aip3_001_action_control.py` 中 `aip_action_approval_event` 绑定 tenant、proposal_id/version/hash、actor、expiry 和幂等键，但无通用 consumed 字段。`aip_action_execution.py::acquire_lease` 在 proposal `FOR UPDATE` 下核准当前 proposal、approvals 与 quorum，生成唯一 attempt=1 lease 并提交；这条通用 lease 是 Action 执行路径，不是策略 Store 发布的自动授权。
3. `ecommerce_growth_cutover.py` 在自身事务内复核 ApprovalEvent hash、Proposal/Draft、actionType、target payload、scope、expiry 和当前批准，再同事务写 cutover/Receipt。这是精确消费范例，不可把任意既有事件跨目标复用。
4. `aip_budget_activation_store.py::precheck_consumption` 核 maker/checker、目标 hash、期限/撤销、当前 head 和外部用量后仍显式 `BUDGET_ACTIVATION_EXTERNAL_USAGE_AUTHORITY_UNWIRED`，没有正式原子消费；不能借预算 decision 给五类策略。
5. `aip_network_policy_store.py::publish` 在同一 `connect` 事务内先读幂等 Receipt，再对新 active 无条件拒绝，草稿路径检查依赖/head、写 revision 和 Receipt、commit。Egress/Data/Quota/BudgetPolicy 的新 active 门同理维持；当前策略不存在精确审批 producer/consumer。

冻结的后续合同：每类固定 ActionType 只能绑定同一 tenant、policy kind/id、下一个 revision、完整目标内容 hash、expected head version、依赖/有效期、预览 hash；maker 与具当前成员资格的独立 checker 审批，BudgetPolicy 保持 R3 两位 checker；决定的 proposal/hash/窗口/撤销与执行 Actor 均重验。Store 必须在锁住 head 和唯一消费键的同一事务内读批准、复算目标、写新 revision、消费记录及幂等 Receipt；失败整体回滚，未知结果先只读对账。历史 active 只读保留。新 schema/ACL 若必要，先独立备份与克隆演练，当前卷迁移另波。

下一波 BG-00bj 先做纯目标规范化/hash 合同（无 Store/DB/当前 ActionType 注册），RED 覆盖跨租户、错 kind/id/revision/head、内容漂移与拼接 ID；随后最小实现和专项/邻接回归。后续再做正式审批来源/产品预览、原子消费及独立安全迁移。当前 approved 安装 binding0、八配置候选0、Host/Owner/自然首链 pending；本波没有业务正向验收。
