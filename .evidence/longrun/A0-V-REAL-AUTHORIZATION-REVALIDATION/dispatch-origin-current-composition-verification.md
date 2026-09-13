# 存储来源与当前权威组合核验

2026-09-13T09:49:47.991314+08:00，基线ece00f74。
FirstDispatchRegistrationService新增validate_registration_origin_in_transaction：固定public表按tenant/receipt_id读取，strict ref重验、原始回执完整性、九项snapshot/目标精确匹配，复用当前配置签名核验。调用前验证SERIALIZABLE/runtime/RLS/scope，调用方拥有事务；不接受历史正文，不提交或登记。

RED 6项新测试因方法缺失失败，原20通过；GREEN Owner PG与来源契约48通过（7.23秒），7既有警告。验证同pid/tx、零新增Receipt、错id/hash/target/scope与当前拒绝。Owner预检/签名节点为编排替身，存储Receipt/SQL/RLS是真实隔离PG，不是主库完整验收。清册1819/158/93五类错误为空，diff-check通过。

未接入Cutover，主库未变。下一波必须让来源和当前配置校验适配正常排空：现有pause使binding revision+1/disabled/fenced，resume最终revision+2；这些应由exact切换回执和阶段状态约束，而不是跳过当前配置/签名。禁止只在prepare检查后就不再检查。随后完成首次fenced切换与撤销。
