# GT-b4c-b2c｜正式费用撤回后 Eval 新占额禁入验证

2026-10-02 04:45 CST；基线 AOS-001092 / m1 `3560293a`，方案 `w5cb4-gtb4cb2c-revocation-plan-20261002.md`。仅 disposable PG；当前真实库 a0v118 只读，无 Provider/Host/worker/Intent。

| 门 | 命令、退出码、结果 |
|---|---|
| 首次专项 | `pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py::test_formal_signed_development_risk_counts_original_eval_hold --tb=short` → exit1，2 passed / 1 failed。失败是测试断言 `ModelEvalBudgetBlocked`，生产实际在原正式费用门以 `BudgetReservationBlocked(BUDGET_COST_CURRENT_RISK_AUTHORITY_REQUIRED)` 拒绝；无放行缺口。 |
| 合同校正 | 测试改断言原费用门异常及原因，附加原三桶链接数量/占额和撤回后第一笔幂等重入检查；未修改生产代码。相同专项 → exit0，3 passed / 7 warnings。 |
| 相邻 | `services/aos-api/.venv/bin/python -m pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py services/aos-api/tests/aip/test_model_eval_request_pg.py services/aos-api/tests/aip/test_budget_cost_consumer_pg.py services/aos-api/tests/aip/test_budget_cost_issuer_pg.py services/aos-api/tests/aip/test_budget_configuration_runtime_pg.py services/aos-api/tests/aip/test_aip_budget_reservation_contracts.py --tb=short` → exit0，64 passed / 7 warnings，54.58s；随后新增幂等重入断言的最终专项再跑 3 passed。 |
| 静态 | `python3 -m py_compile services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py` 与 `git diff --check` → exit0。 |

正式签名预算允许两笔；第一笔 Eval hold 落账后，撤回前 `require_cost_risk(new_hold=True)` 可通过。原 maker 经签名 issuer 撤回后，另一个原 Model 申请/审批的 hold 被原正式费用门拒绝且无新行；第一笔继续 `held`，三个桶链接总占额仍为三倍单笔上界，第一笔同身份调用只返回既有 hold。结果证明撤回后的**新预留禁入与已持有账本保留**，没有证明已发出未知结果或自然到期行为。

未完成：真普通 Task/Eval 同预算并发、独立 Policy/Price 漂移注入、自然到期、`unknown` 账本状态与物理 Provider 容量共同锁、一次 Intent、真实栈迁移/重启及首条业务链。`test_content_first_action_binding_pg.py` 明确替代业务源，不能冒充自然正向；Goal 继续 active。
