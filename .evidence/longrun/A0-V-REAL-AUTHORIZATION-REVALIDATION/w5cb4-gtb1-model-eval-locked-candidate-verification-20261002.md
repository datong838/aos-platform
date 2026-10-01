# GT-b1 第一切片：Model 首评候选同事务锁定读验证

基线 AOS-001084 / m1 `ad6d3477`，Task `W5CB4-GTB1-MODEL-EVAL-FORMAL-OWNER-20261002`。本检查点只新增可供未来申请/批准/发送意图写事务调用的 Model 候选 reader；**不构成 GT-b1 正式 Owner 完成**。

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_model_eval_authorization.py -k 'current_candidate_is_rechecked or locked_candidate_rejects_drift' --tb=short`（实现前） | 1 | 8 failed：Store 缺同事务方法；RED 有效 |
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_model_eval_authorization.py services/aos-api/tests/aip/test_aip7_model_runtime_store.py services/aos-api/tests/aip/test_aip_model_runtime_resolver.py --tb=short` | 0 | 38 passed、7 个既有 warning；锁定 reader 的 9 个组合覆盖当前值与缺行/head/source/target/tenant/row hash/payload hash/lifecycle 漂移 |
| `python3 -m py_compile services/aos-api/aos_api/aip_model_runtime_store.py services/aos-api/tests/aip/test_model_eval_authorization.py` | 0 | 语法通过 |
| `git diff --check` | 0 | 无空白错误 |

代码/方案复审：方法只接受调用方连接，不自行开启/提交事务；SQL 锁 `aip_registered_model_head h` 并读取当前 revision，精确核 canonical payload、租户和 next-active target。它不读预检对象、不写 EvalRun/预算/容量、不调用 Provider。测试用受控 connection 对 SQL/拒绝路径做契约验证；尚未做独立 PG 行锁并发验证，也没有集成正式申请/批准事务。当前权威库仍只读 118、代码迁移头 132；本波未迁移、重启或开 Host。

新审计结论：原容量池发布要求 Route/Model/Provider 全 active，首评 draft/validated Model 不能直接占原 exact route 池。下一段需要证明评测与普通运行共享物理容量上界和事务锁，不能用独立评测池假装安全。原预算预留要求真实 Task；也不能伪造。以上均保留为 GT-b 正式 Owner 的未完成项。
