# s3o-w-r｜六 Agent 行锁与原 BI Plan/Receipt 隔离正向

- 基线 `m1@cf018b11`、Authority `AOS-001230`、代码/当前库 `a0v_135`；依据 231-3、231-9、D-wave s3o-w-r 与本波文件级方案。真实当前库只读、Host/worker/Provider关。
- RED：上波原签名 Growth1.13 全 schema 一次性库以独立非 owner `aos_bi_plan_issuer` 调原 `SignedBIPlanPreparationService.prepare`，六 Agent 的 `aip_agent_instance FOR SHARE` SQLSTATE42501；Plan/BI Receipt0。
- 最小实现：测试库新增 `aos_bi_plan_agents_lock_a0v_136`，只在精确发行 `session_user` 与租户 GUC 一致、请求六个互异 ID 时返回当前同租户 active Agent 的 ID/version 并持 `FOR SHARE`；`PUBLIC` 撤权、仅该发行角色 EXECUTE。原 prepare 仅对真实 PG 精确 `current_user` 走函数，其余原 SQL 不变。测试专用 Receipt guard 加入 `bi_responsibility_plan.prepare`，仍须与原 PlanRevision ID/revision/hash 配对，不降配对强度。
- 正向：原签名全 schema `1 passed` exit0。非 owner 登录下原 prepare 产生 1 Plan/1 配对 BI Receipt，同键重放返回同一 Plan 且不增行；版本改为2后同键 request drift 触发原 `ProductionContractIdempotencyConflict` 且原 Receipt仍1。
- 负向：少于六 ID、重复 ID、错租户、冒用数据库角色均拒；将一 Agent 停用后原 prepare 报“six current digital coworker instances required”，新键 Receipt0。持锁事务期间并发停用 Agent 在 150ms `lock_timeout` 下拒绝，释放后可改。测试对象和改动只在一次性库，并恢复测试行状态/版本。
- 相邻 BI/安装/当前权限共 `97 passed` exit0；`py_compile` 和 `git diff --check` exit0。当前数据库 `aos_bi_plan_issuer`、四个 test-only 函数、`aos_test_*_ti4_test` 残留均0，当前 Plan/BI Receipt0。
- 复审边界：一次性签名安装、测试专用六 Agent 和发行函数不等于当前正式身份/来源；函数内部仅按六互异 ID 过滤，正式落库还须收紧为授权的六精确 ID 或签名来源引用，并经新备份、全链克隆和零执行窗口。正式配置八类、Host assignment/identity、Tool durable source 与首条业务链仍未完成。
