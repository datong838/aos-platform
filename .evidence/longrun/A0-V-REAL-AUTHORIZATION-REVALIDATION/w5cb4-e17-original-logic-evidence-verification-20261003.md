# W5CB4 E17-s3c｜原 Logic Eval 证据生产链隔离验证

## 实测路径与退出码

- 原 `LogicGraphStore.create` → `LogicRunStore.start_run/finalize_run` + `LogicDryRunExecutor.execute` → `EvalEvidenceStore.create_suite` + `routers/evals._run_and_persist` → 原 `LogicEvalEvidenceReader` → `LogicPublicationStore.publish`，均在 test-only PG 临时 schema，未写当前权威库。
- 发布前缺 Report：`LogicPublicationEvalEvidenceRequired`，publication 0；错误 Report 同样拒，跨租户无 Graph 拒，publication 仍0。原 Eval 正向 Report 的 gate passed；发布行精确回读 Graph hash、Report id、dry-run id，同键重放只保留1行。
- 初次新增专项退出1：隔离 PG `started_at` 比测试进程 `finished_at` 领先毫秒，触发 `LogicDryRun` 时间顺序校验。只在既有测试 helper 设定 `now >= started_at + 1ms`，不改生产时钟或真库数据。此后新增专项1 passed。
- `uv run --no-sync pytest -q -o log_cli=false tests/test_aip_logic_publication_store.py tests/test_aip_eval_store.py` 退出0：19 passed；`tests/test_evals_engine.py` 退出0：17 passed、1 skipped。`git diff --check` 与 `py_compile` 退出0。当前 venv 无 ruff，`uv run --no-sync ruff check ...` 退出2 (`Failed to spawn: ruff`)，未当作通过。

## 一致性与边界

- 代码只改 `tests/test_aip_logic_publication_store.py`：测试从直接插 Suite/Report 的 FakeReader 正向扩展为原生产 API/Store 正向；现有 FakeReader 负例保留。生产签名门与默认禁入逻辑均未改。
- 这证明原 Logic 发布证据消费链在隔离库可运行，不证明当前六个 Skill 有正式 Logic、ModelRoute/RuntimePolicy、Skill Eval 身份、八配置或首链。当前库 `aos_current_preview_20260927@a0v_135` 保持只读；Host/worker/Provider关闭。
- 下一波 E17-s3d 先审原 Model Eval Gate/Route/Policy 的独立合法生产入口与当前缺口；若正式 Model Eval Owner 尚缺，转八配置中不依赖它的合法生产者最小项。不得直接插 active 行或借测试夹具宣称当前发布。
