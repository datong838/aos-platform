# W5CB4 E17-s3d｜原 Model Eval Gate 与 Route/Policy Owner 审计方案

## 上位与文件事实

- 按 231 与 E17-s3b/s3c，Skill 最终发布必须引用当前原 ModelRoute/RuntimePolicy；不得将测试授权夹具或 Skill Gate 充当 Model Gate。
- `aip_model_runtime_store.py` 的 active Route 先调用 `AipEvalAuthorityStore.require_exact_passed`，并传 `evaluation_candidate_ref(route)`；active RegisteredModel 同理。Policy 原入口先核 NetworkPolicy、GuardPolicy、GovernancePolicy。`aip_eval_runner.py` 对 RegisteredModel/ModelRoute 目标在 `run_by_contract` 和 `run` 均显式拒绝，当前没有正式执行 Owner。
- 本波只在既有 test-only 合同中补 active Route 原发布入口的精确失败封闭测试，并查完整依赖图；不删除硬拒、不插当前或隔离 active 行、不启动 Provider/Host。

## 文件级施工

1. `services/aos-api/tests/aip/test_aip7_model_runtime_store.py`：沿已有 `_RejectEvalGate` 和 `hashed(ModelRouteRevision)` 构造 active Route，断言在写 Store 前以 exact Model Gate 拒。保持原 validated Route 的既有路径。
2. `services/aos-api/aos_api/aip_model_runtime_store.py`、`aip_model_eval_authorization.py` 只读复审；若发现真实代码缺陷再另开精确方案和测试，不为满足测试放宽门禁。
3. 运行专项及 Route/Policy 相邻回归、py_compile/diff；记录正式 Owner/模型评测申请与执行之间的缺口、已排除替代路径，更新权威与下波八配置独立项。

## 边界

当前权威库只读；test-only 单测不构成 Model Gate 当前正式授权。org-org/dev-project 为唯一正向租户，dev-org 只隔离 canary；无商城源读取、旧 Run 回放、手工 run_definition 或 push。

## 验证与结论

- 新增 active `ModelRouteRevision` 原 `publish_route` 调用的失败封闭测试：注入明确拒绝 exact gate 的 authority，在任何 Store 写之前得到 `ModelRuntimeDependencyBlocked`。该测试只锁住原入口的行为，不证明正式 Model Gate 已产生；原 validated Route 相邻测试保留。
- `uv run --no-sync pytest -q -o log_cli=false tests/aip/test_aip7_model_runtime_store.py tests/aip/test_model_eval_authorization.py tests/aip/test_model_eval_request_pg.py` 退出0，38 passed；`git diff --check`、`py_compile` 退出0。
- 原 `AipModelEvalRequestStore.create` 是精确申请，无 Provider/Run 调用；`ModelEvalActionGuard` 要当前 Owner、OIDC maker/独立 checker、审批绑定；这些都是执行前治理，不会生成 PASSED Eval Gate。`AipEvalRunner.run_by_contract` 和 `run` 对 RegisteredModel/ModelRoute 双硬拒（源文件行133/218）。`publish_route(active)` 需要它的 exact Model Gate；`publish_policy` 独立要求 Network、Guard、Governance 当前依赖。现有 `test_aip7_model_runtime_store.py` 正向使用历史测试 Guard/Governance/Network 夹具，发布的是 validated Route，不能算当前 active 正链。
- 未改生产门禁，未写当前真实库。局部 Model Gate 正链缺正式执行 Owner，E17-s3e 转八配置中独立合法生产者；正式 Owner 到位后再返回 Model Gate→active Route/Policy→Skill 发布。
