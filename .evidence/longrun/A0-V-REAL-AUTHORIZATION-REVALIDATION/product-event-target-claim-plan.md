# 事件分析承接：精确目标领取前置方案

基线 m1@39e03945。沿用父任务 A0-V-REAL-AUTHORIZATION-REVALIDATION 的 Host/tests 范围。

目标仍是同一真实经营首链。本子波先避免安装处理器领取同租户另一安装或另一操作的任务；不声称分析 Run 已接通。

修改文件：
- services/aos-api/aos_api/automation_occurrence_store.py：新增不可变精确 ClaimTarget(operation_id, installation_id, generation)，claim_next 可选 target；过滤在领取 SQL 内完成，不能领取后再判断。
- services/aos-api/tests/extension_runtime/test_automation_occurrences_pg.py：真实隔离 PostgreSQL 证明错安装/代次/操作不领取、不创建 attempt，正确目标领取且仅一次。

保持未传 target 的原接口、RLS、当前绑定/禁入/租约和 Receipt 流程不变。新参数不是授权，仍须既有全部门禁。无迁移、主库写入、Host 重启或 push。自测后核对 AR2 清册，回滚仅本子波代码。下一子波连接异步 installed package 分析命令与当前 Receipt/claim 复核。
