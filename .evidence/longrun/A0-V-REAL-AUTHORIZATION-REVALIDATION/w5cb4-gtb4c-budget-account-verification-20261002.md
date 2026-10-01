# GT-b4c-a 共用预算账户合同验证

2026-10-02 03:40 CST；基线 AOS-001088 / m1 8a429017。先复习 231-5 第6节、AIP 模型供应容量与成本治理、BG00GT 与 GT-b4a 方案，再修改 `aip_budget_reservation_contracts.py`；范围仅账户派生，不含占额/发送。

| 步骤 | 命令/输出 | 结论 |
|---|---|---|
| RED | `pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_bucket_contract.py --tb=short` → exit 2，`ImportError: cannot import name 'derive_model_eval_bucket_authorities'` | 新合同未实现，RED 可复现 |
| GREEN 与相邻 | `pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_budget_bucket_contract.py services/aos-api/tests/aip/test_aip_budget_reservation_contracts.py --tb=short` → exit 0，15 passed/7 warnings | 新 Eval 身份和原业务三桶派生合同一致；未伪造 Task |
| PG 适用性 | 追加 `test_aip_budget_reservation_pg.py` → exit 0，15 passed/10 skipped/7 warnings；文件要求 `AOS_EXTENSION_PG_TEST=1` 及独立 PostgreSQL opt-in | 未把 skipped 当成 PG 通过；本波无 DB 写逻辑，纯合同测试已覆盖改动 |
| 静态 | `python3 -m py_compile` 两文件、`git diff --check` → exit 0 | 无语法/空白错误 |

代码把原 `derive_bucket_authorities` 的时间窗算法原样移到共享内核；普通 API 和输出不变。新 Eval API 要求真实 `BudgetRevision` 型精确引用、有效上界、规范申请 ID；`model-eval/<request_id>` 禁 `:`，与普通 `operation_id:task_id` 账户名分离。首评日/月账户仍由相同 BudgetRevision ID 派生。测试覆盖同账本键、不同预算隔离、失效/不规范输入。

风险仍在：合同不证明 Model BudgetPolicy/current BudgetRevision/原 checker 审批的 DB 绑定，不写 `aip_budget_bucket`，不预留容量，不建 Intent。物理 Provider 额度权威尚缺；普通执行和首评发送门不变。下一步在 disposable PG 中建立申请/审批/预算原桶同事务占额及并发争抢，然后与物理容量合并；当前真库 a0v_118 只读，不迁移或重启。
