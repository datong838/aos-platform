# GT-b4c-b2b｜正式开发风险含 Eval hold，精确模型费用绑定

2026-10-02 04:31 CST；基线 AOS-001091 / m1 `4cea78e4`。方案：`w5cb4-gtb4cb2b-formal-risk-plan-20261002.md`。真实权威库 a0v118 只读；本次仅在 pytest 自动创建并销毁的 disposable PG 写入，未启动 Host、worker 或 Provider。

| 门 | 命令、退出码与结果 |
|---|---|
| RED | `pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py::test_formal_signed_development_risk_counts_original_eval_hold --tb=short` → exit1，1 passed / 1 failed：错 `providerModelId` 的 Eval hold 未拒绝，证明 b2a writer 缺精确费用模型绑定。 |
| 最小修复 | `services/aos-api/aos_api/aip_model_eval_budget_reservation.py` 在原 Model/Price/Policy 当前权威复验后，比较持久 Model 与 Price 的 hash、Policy/Price 正式费用授权一致性，并核其 Provider、模型 ID 和租户与申请精确一致；不改原普通 Task Store、不放宽授权。 |
| 专项 | 相同参数化测试 → exit0，2 passed；正式签名 proposal→checker decision→受限消费→预算激活→Policy/Price 派生→原 Model Eval 申请/审批→hold；错模型 ID 失败封闭且零 Eval hold。 |
| 相邻 | `services/aos-api/.venv/bin/python -m pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py services/aos-api/tests/aip/test_model_eval_request_pg.py services/aos-api/tests/aip/test_budget_cost_consumer_pg.py services/aos-api/tests/aip/test_budget_configuration_runtime_pg.py services/aos-api/tests/aip/test_aip_budget_reservation_contracts.py --tb=short` → exit0，47 passed / 7 warnings，39.27s。 |
| 静态 | `python3 -m py_compile` 三个相关文件与 `git diff --check` → exit0。 |

正向已持久 Eval hold 后，原 `require_cost_risk` 对 `new_hold=True` 按 `max_requests=1,total_risk_minor=per_request` 拒绝；`new_hold=False` 重验通过。证明正式风险门计入 Eval hold；未证明普通 Task 与 Eval 共享桶的双路径正向并发。正式费用授权的 Provider/model/tenant 精确交点已增加 fail-closed 检查，且历史无费用授权的原测试保持通过。

剩余：真普通 Task/审批合法 Action 绑定来源尚未就绪，不能手写桶数字冒充它；正式授权撤回/过期与独立 Policy/Price 漂移注入仍需专项；GT-b4b 物理 Provider 共同容量及一次 Intent、真实库迁移/完整重启、Provider 自然评测和首条经营闭环均未完成。此波不使当前运行实例获得发送许可。
