# GT-b2 Model Eval head PostgreSQL 行锁补证

基线 AOS-001085 / m1 `ea173ef1`，Task `W5CB4-GTB2-MODEL-EVAL-PG-HEAD-LOCK-20261002`。本波只追加 test-only PG 集成测试，无生产代码或当前库迁移。

预检：`aos_api.db.get_dsn()` 实际连接 host `127.0.0.1`、port `5433`、dbname `aos_meta`、user `aos_app`；它是 test-only PG，不是当前权威 `aos_current_preview_20260927`。未输出凭证。测试记录以唯一 `test:aip7-store:<uuid>` 发布并由既有 finally cleanup；事务中的 head version 修改回滚。

| 验证 | 退出码 | 结果 |
|---|---:|---|
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip7_model_runtime_store.py -k store_persists_exact_chain --tb=short` | 0 | 1 passed、2 deselected；holder 调用 locked reader 后，contender 对同一 head 的 `FOR UPDATE` 在 250ms lock_timeout 下抛 `LockNotAvailable`；holder rollback 后 contender 成功 |
| 初次加入 head-version 断言的三文件回归 | 测试退出 1 | 1 failed/37 passed：测试缺 `ModelRuntimeConflict` import；已定位并修复，不是生产逻辑故障 |
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip7_model_runtime_store.py services/aos-api/tests/aip/test_model_eval_authorization.py services/aos-api/tests/aip/test_aip_model_runtime_resolver.py --tb=short` | 0 | 38 passed、7 个既有 warning；同事务把 head.version 增 1 时 reader 拒绝旧 expected version，随后回滚 |
| `python3 -m py_compile services/aos-api/tests/aip/test_aip7_model_runtime_store.py`、`git diff --check` | 0/0 | 语法及差异检查通过 |

方案/逻辑复审：测试无 Provider 回调、无 Model active 晋升、无 Approval/预算/容量/intent；只证明 GT-b1 reader 的数据库锁和 head 漂移行为。GT-b 正式 Owner、共享物理容量上界、费用预留和发送意图仍未实现。API/Web 今日完整最新栈重启仍待独立安全门。
