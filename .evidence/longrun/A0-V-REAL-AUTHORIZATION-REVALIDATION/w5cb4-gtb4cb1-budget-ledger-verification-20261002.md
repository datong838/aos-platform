# GT-b4c-b1｜独立 Eval 预算账本基础验证

2026-10-02 03:59 CST；基线 `m1 8319189b` / AOS-001089。先读 231-5 §6、228 AIP 模型容量费用方案、GT-b4a/c-a 方案及原预算/Action/申请实现，文件级方案见 `w5cb4-gtb4cb-budget-hold-plan-20261002.md`。本子波不实现 hold writer，不授权任何 Eval/Provider 调用。

| 检查 | 本次命令及退出码 | 证明范围 |
|---|---|---|
| RED | `services/aos-api/.venv/bin/python -m pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py --tb=short` → exit 1，`len(rows)==0` | disposable PG 当前无独立 Eval 预留表 |
| 迁移与相邻 | 同命令追加 `test_model_eval_request_pg.py` → exit 0，`15 passed, 7 warnings` | 一次性 PG 从零迁移至 `a0v_134`，新增两表、RLS/最小权限/append-only 元数据，原申请/审批测试仍通过 |
| 正式费用门相邻 | `test_budget_cost_consumer_pg.py test_aip_budget_reservation_contracts.py` → exit 0，`20 passed, 7 warnings` | 新风险合并 SQL 在空 Eval 账本下不破坏原正式费用门和预算合同；**尚未证明有 Eval hold 时的额度争抢** |
| 静态 | `python -m py_compile` 三个改动文件、`git diff --check` → exit 0 | 语法/空白无异常 |

代码复审：`a0v_134` 新增与普通 Task 预留分离的两张表，申请与原批准事件有复合租户 FK，`request_id`、`approval_event_id` 各自租户唯一；RLS FORCE、追加写触发器和 `aos_runtime` SELECT/INSERT，未改普通 Store 的真 Task 门。`require_cost_risk` 在原正式 fence 锁/写之后，对同一 `BudgetRevision` 合并普通和 Eval 预留计数；新表在迁移前不存在时会失败关闭。未增发送、释放或未知状态迁移。

**未完成/下一项**：GT-b4c-b2 必须在 disposable PG 用真实持久 ModelEvalRequest + 原 maker/checker ApprovalEvent 建事务绑定 writer；对当前 head/BudgetPolicy/BudgetRevision/Price 复验并锁三桶，测试同申请幂等、普通与 Eval 并发限额、正式 `max_requests/total_risk_minor` 包含 Eval 行、失败全回滚、隔离和未知保留。未完成前本账本无 Eval row，不能称“共桶占额已完成”。之后仍需 GT-b4b 正式 Provider 物理上限和统一容量锁、一次 Intent/transport/Usage/Report/Gate。当前真实库仍 `a0v_118` 只读，对代码头 `a0v_134`；今天最新栈完整重启另需当日备份、克隆全链与零执行门，未完成。Host/worker/Provider 关闭，首链 pending。
