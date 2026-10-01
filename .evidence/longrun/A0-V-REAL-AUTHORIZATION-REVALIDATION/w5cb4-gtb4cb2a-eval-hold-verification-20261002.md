# GT-b4c-b2a｜原审批绑定的 Eval 共桶 hold 验证

2026-10-02 04:17 CST；基线 AOS-001090 / m1 `7014ddd7`。依据 `w5cb4-gtb4cb-budget-hold-plan-20261002.md` 继续，真实权威库 a0v118 只读；仅 disposable PG，Host/worker/Provider 未启。

| 步骤 | 命令/退出码 | 证明 |
|---|---|---|
| RED | `pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py::test_approved_model_eval_holds_real_shared_budget_buckets_once --tb=short` → exit1，`ModuleNotFoundError: aos_api.aip_model_eval_budget_reservation` | 当时无事务绑定 writer |
| 排障 | 初次实现报 `permission denied` 于 immutable 申请的 `FOR SHARE`、append-only hold 的 `FOR UPDATE`；仅删除这两处不必要行锁，保留可写 proposal 锁和原共享桶锁 | 使用运行角色的实际 DB 权限，未扩权；唯一键与 SERIALIZABLE 守护重复申请 |
| 专项与相邻 | `services/aos-api/.venv/bin/python -m pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py services/aos-api/tests/aip/test_model_eval_request_pg.py services/aos-api/tests/aip/test_budget_cost_consumer_pg.py services/aos-api/tests/aip/test_aip_budget_reservation_contracts.py --tb=short` → exit0，**40 passed/7 warnings** | 真持久 Model 申请及原 maker/checker 批准、同申请重入只占一次、错批准拒绝、事务异常全回滚、不同 Eval 同日桶顺序及两线程争抢最多一个成功、dev-org 零行、非 SERIALIZABLE 拒绝；原申请和费用门相邻通过 |
| 静态 | `python -m py_compile` 四个相关代码/测试文件、`git diff --check` → exit0 | 语法/空白无异常 |

逻辑复审：writer 不开/提交连接、不产生 Provider 调用、Intent/Task/AgentRun。进入时强制当前 `aos_runtime`、租户 GUC 和 SERIALIZABLE；原 Action proposal 当前 approved、版本/hash/binding 与未过期 checker 事件精确核对，并复用 `ModelEvalActionGuard` 复验 Model/Price/治理依赖；当前 BudgetPolicy 指向真 BudgetRevision，原三桶按共享锁排序占额。原 `AipBudgetReservationStore.reserve` 的真 Task 门未改。`shared_risk_totals` 在持久 Eval hold 后读得 `(1,200)`，正式费用门相邻测试通过，但本次 fixture 为历史预算，**尚未用正式开发风险提案实测 `max_requests/total_risk_minor` 含 Eval 行**。

**未完成**：GT-b4c-b2b 仍须真普通 Task/Approval 与 Eval 同一 BudgetRevision 并发争抢、正式开发费用风险额正反、撤回/过期以及 RLS/幂等冲突覆盖。当前 writer 只建 `held`，无提交/unknown/release 状态机；不能用于 Provider 发送，余额不能因 TTL 自动归零。GT-b4b 物理 Provider 共同容量/Owner、一次性 Intent、transport/Usage/Report/Gate 和真实当前实例仍待。代码头 a0v134 对真库 a0v118，当日完整重启另门 pending；本波不能称首链或 b2 全部完成。
