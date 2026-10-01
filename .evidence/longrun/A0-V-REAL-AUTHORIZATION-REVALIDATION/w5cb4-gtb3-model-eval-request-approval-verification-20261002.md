# GT-b3 首次 Model Eval 申请 / 原 maker-checker 绑定验证

基线 `m1 62b0fcda` / AOS-001086；Task `W5CB4-GTB3-MODEL-EVAL-REQUEST-APPROVAL-20261002`，执行器补丁独立 Task `W5CB4-GTB3-EXECUTOR-FENCE-20261002`。本证据只证明代码与自动创建的 disposable PostgreSQL；当前权威库只读、未迁移至 a0v_133、未启 Provider/Host。

## 方案与改动回读

- 已复习 231-5 真实调度审批预算恢复、BG00GT 清单、GT-a/b0/b1/b2、原 ActionStore/Policy/Executor、ModelRuntime 与 Eval Suite/Contract 源码。文件级计划见 `w5cb4-gtb3-model-eval-request-approval-plan-20261002.md`；`AssetRevisionRef` 与 `VersionedAssetRef` 的类型/revision 映射按计划显式比对。
- `a0v_133_model_eval_request.py` 建不可变 tenant RLS 申请表，注册并保留专用 ObjectType/ActionType；没有执行状态。`aip_model_eval_authorization.py` 限定 Model source→next-active target、purpose=`quality-eval`、CNY、正费用上界和有时区截止。
- `aip_model_eval_request_store.py` 以租户 SERIALIZABLE 事务锁当前 Model head，重读 exact Model/Provider/Price/Quota/Budget、Suite target 与冻结 Contract；同键同 hash 返回原申请。`aip_model_eval_action.py` 在 Action 写事务重验原申请与依赖、当前元数据和成员角色，maker/checker 分离；`aip_action_policy.py` 固定 R2、makerChecker、`executionAllowed=false`；`aip_action_store.py` 对无专用 Guard 失败封闭；`aip_action_execution.py` 在领取 lease 前拒绝此 ActionType。

## RED / GREEN

| 验证 | 命令或输出 | 结果 |
|---|---|---|
| 契约 RED | `pytest .../test_model_eval_request_pg.py --tb=short`，缺 `ModelEvalRequestCreate` | ImportError，exit 2 |
| 风险 RED | `...pytest -k explicit_approval` | 旧分类 R3、`executionAllowed=true`，1 failed，exit 1 |
| Store RED | `...pytest -k missing_current_model` | 新 Store 缺失，collection error；随后首次真实 PG 重验抛原 `ModelRuntimeConflict`，1 failed |
| Action RED | `...pytest -k generic_action_store` | 原通用 Store 没有拒绝专用 Action，1 failed |
| Executor RED | `...pytest test_model_eval_execution_gate.py` | 三种 id/snapshot 组合均未拒绝，3 failed |
| 最终专项与相邻 | `services/aos-api/.venv/bin/pytest -q -o log_cli=false services/aos-api/tests/aip/test_model_eval_request_pg.py services/aos-api/tests/aip/test_model_eval_execution_gate.py services/aos-api/tests/aip/test_model_eval_authorization.py services/aos-api/tests/aip/test_aip7_model_runtime_store.py services/aos-api/tests/aip/test_aip_policy_activation_action.py services/aos-api/tests/aip/test_aip_policy_action_proposal_gate.py services/aos-api/tests/test_actions_execute.py --tb=short` | exit 0，54 passed / 7 warnings；log `/tmp/aos-gtb3-final-pytest.log` |
| 语法/空白 | `.venv/bin/python -m compileall -q` 精确新旧改动 Python 文件；`git diff --check` | exit 0 |

pytest 的 `services/aos-api/tests/conftest.py::_isolated_postgres_database` 每次创建并在结束时删除独立 `aos_test_*_ti4_test` 库，完整 Alembic 自动迁至 a0v_133。正向测试只用该库的人造 Model、正式 quota 测试签名链和 synthetic Suite/Contract；证明精确申请、同键重放、错 hash/租户/head/metadata/maker-checker 拒绝、DB append-only；批准后执行 lease/EvalRun/Report/Gate 均为 0。它不是当前真实租户 Provider 授权或首链成功。

## 方案一致性、风险及下波

方案约束已逐项落到代码和测试；浏览器未改页面，本波不适用。原通用 Action 仅产生批准事件，不产生 Provider call、BudgetReservation、CapacityReservation 或发送意图。GT-b4 必须接现有预算桶与共享物理容量上界，定义真正有界的一次发送 Intent；当前价格政策可批准申请，不代表费用已预留。Provider 健康、Secret/transport、独立执行签名、Usage/Report/Gate 与自然首链仍无正向当前证据。当前权威库 a0v_118 对代码 a0v_133，迁移/最新栈重启必须走独立备份、恢复克隆和零执行门。Goal 保持 active，E16 禁入/E17 首链 pending。
