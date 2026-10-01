# GT-b4a 共享物理容量缺口：隔离 PG RED 与方案复审

2026-10-02 03:23 CST；基线 `m1 7eed628e` / AOS-001087。先读 `231-5`、BG00GT、`aip_budget_reservation_{contracts,store}.py`、`aip_model_capacity_{authority,reservation}.py`、`aip_model_governance_policy_contracts.py` 和 `a0v_133`；设计见同目录 `w5cb4-gtb4-shared-ledger-plan-20261002.md`。

## RED 与相邻验证

| 命令 | 退出 | 新证据 |
|---|---:|---|
| `services/aos-api/.venv/bin/pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_shared_capacity_pg.py --runxfail --tb=short` | 1 | 2 failed，均为 `Failed: DID NOT RAISE AipAgentRegistryTransitionBlocked`。有 Route 池而无物理 Provider 账户照样准入；同 Provider 两个 Route 池各可占一份，未共享物理计数。 |
| `services/aos-api/.venv/bin/pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_shared_capacity_pg.py services/aos-api/tests/aip/test_aip7_capacity_reservation_db.py --tb=short` | 0 | `1 passed, 2 xfailed, 7 warnings`；原池内 101 并发最多 100 的相邻行为仍通过，两条 GT-b4 目标断言以 strict xfail 保留，不能当 GREEN。 |

隔离 PG 由 pytest 自动建立并迁移到 `a0v_133`；仅测试数据。第一次复跑时复用了原容量测试的固定池身份，导致同一模块组合测试冲突；已改为独立 `test:gtb4:*` 池/Route/Model，并再次复跑到上述结果。没有触当前权威库、Provider 或 Host。

## 方案/逻辑/风险复审

- 已确认 Model `BudgetPolicyRevision` 持有 `BudgetRevision` 精确引用；Eval 日/月账户可与普通业务使用同一 BudgetRevision ID 和原 `aip_budget_bucket`。但现有 `ReserveBudgetRequest`、`_task_authority` 和 `_approval_authority` 强制真实 Task，不能把首评申请强转为 Task。
- 已确认普通容量门以 exact Route 池 head 为锁/计数键，ProviderRevision 无物理并发上限字段。`QuotaPolicyRevision.maxConcurrency` 是 Model 配额，不具备可直接当作 Provider 物理上限的证明。新增 Provider 容量权威必须给出正式 owner、额度来源、期限与发布/变更审批；缺时 fail-closed。
- 无物理账户、无共同预算预留、无一次性 Intent：GT-b4 尚未实现，两个 strict xfail 是明确开发债而非通过。真实 Model Eval 审批仍不可执行，当前真实库停留 `a0v_118`、代码 `a0v_133`，今日最新栈重启独立进行。
- 下一最小实现入口：先确定正式 Provider 物理账户来源及双用途共享迁移策略；在同一 disposable PG 上让两个 xfail 转 GREEN，然后验证普通 101 并发、跨 Route 池、Eval/普通争抢与 RLS。预算/Intent 在后继独立波，不与本 RED 混称完成。
