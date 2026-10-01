# GT-b4c-b2d｜Model Eval 原申请自然到期与旧 hold 保留

2026-10-02 05:19 CST。基线 AOS-001095 / m1 `69ddd03b`；方案 `w5cb4-gtb4cb2d-natural-expiry-plan-20261002.md`。本波只改测试 helper 与 PG 测试；默认30分钟不变，独立用20秒短时申请。原 Store 持久 ModelEvalRequest、maker/checker ApprovalEvent、原 Eval hold；无时间 mock、无手工数据库状态修改。当前权威库118只读。

| 门 | 命令/退出码/结果 |
|---|---|
| 专项 | `services/aos-api/.venv/bin/python -m pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py::test_natural_eval_expiry_blocks_new_hold_and_keeps_prior_hold --tb=short` → 初轮 exit0，1 passed/7 warnings，26.05s；复审后加强为三桶逐项断言，并在末轮两文件复跑。真实到期后原已 hold 和未 hold 申请均拒绝新/重入占额；原 hold 行仍 held，三桶 held 未减，未 hold 行0。 |
| 相邻 | 同 pytest 加 `test_model_eval_budget_reservation_pg.py`、`test_model_eval_request_pg.py`、`test_budget_cost_consumer_pg.py`、`test_budget_cost_issuer_pg.py`、`test_budget_configuration_runtime_pg.py`、`test_aip_budget_reservation_contracts.py` → 初轮 exit0，67 passed/7 warnings，78.12s。末轮只改三桶断言，复跑 `test_model_eval_budget_reservation_pg.py` 与 `test_model_eval_request_pg.py` → exit0，26 passed/7 warnings，36.94s。 |
| 静态/复审 | 两个修改的测试文件 `py_compile` 与 `git diff --check` → exit0。helper 默认值仍30分钟、正式来源的原最小未来时间断言不变；原生产代码和 schema 不变，浏览器不适用。 |

结论仅为 disposable PG 的真实到期失败封闭与旧 `held` 占额保留；不证明已发出 `unknown`，因为 Eval 预算 schema 当前只允许 `held` 且尚无一次性 Intent/Provider 发送。后续 GT-b4b/Intent 状态机建立后再测试 unknown 对账。合法普通 Task 自然来源、当前118→134迁移与今日完整重启、自然首链均待。
