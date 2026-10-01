# GT-b4c-b2d｜Price/Policy 当前 head 漂移后旧 Eval 预算禁入

2026-10-02 05:07 CST，基线 AOS-001094 / m1 `5fcc5926`。方案 `w5cb4-gtb4cb2d-price-policy-drift-plan-20261002.md`。测试只写 pytest disposable PG；真实权威库 `a0v_118` 只读、Host/worker/Provider关闭。

| 门 | 命令/退出码/结果 |
|---|---|
| 方案/测试 | 扩展 `services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py`，先用原持久 ModelEvalRequest 与 maker/checker Action 审批；Price 分支经原 `AipModelRuntimeStore.publish_price_snapshot` 发布同 ID revision2，Policy 分支经原 `AipModelGovernancePolicyStore.publish_budget` 发布同 ID draft revision2。没有直接改头表、手写 ApprovalEvent 或预算桶。 |
| 专项 | `services/aos-api/.venv/bin/python -m pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py::test_approved_eval_cannot_hold_after_current_price_or_policy_head_moves --tb=short` → exit0，2 passed/7 warnings。两分支原 Eval hold 都由原 Action 当前申请校验 fail-closed，Eval hold 行0、对应预算账户 held0。原逻辑已正确拒绝，无生产修复。 |
| 相邻 | 同 pytest 加 `test_model_eval_budget_reservation_pg.py`、`test_model_eval_request_pg.py`、`test_budget_cost_consumer_pg.py`、`test_budget_cost_issuer_pg.py`、`test_budget_configuration_runtime_pg.py`、`test_aip_budget_reservation_contracts.py` → exit0，66 passed/7 warnings，56.88s。 |
| 静态 | `python3 -m py_compile services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py` 与 `git diff --check` → exit0。 |

这证明独立 Price 或 BudgetPolicy head 变更发生在原批准之后、预算 hold 之前时，旧申请不能新占额。Policy 新 revision 为 draft，因为 active 发布必须有独立正式批准；测试不绕过该门。它不是自然业务首链或当前正式身份验收。

仍待：合法普通 Task/Action 自然来源与 Eval 同桶并发正向；自然时间到期、已发出 unknown 的不释放/对账；GT-b4b 正式 Provider 物理容量共同锁与 Intent；当前118→134零执行切换及今日最新栈重启。克隆134仅证明可恢复迁移，不能代替当前实例。
