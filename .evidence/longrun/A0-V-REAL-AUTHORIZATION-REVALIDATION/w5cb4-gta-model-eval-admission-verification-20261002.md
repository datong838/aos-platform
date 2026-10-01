# GT-a Model 首评用途预检 verification

基线 AOS-001082 / `m1@ac022438`；Task `W5CB4-GTA-MODEL-EVAL-ADMISSION-20261002`。上位与文件级方案：`w5cb4-bg00gt-model-eval-bootstrap-plan-20261001.md`、`w5cb4-gta-model-eval-admission-plan-20261002.md`。

## RED / GREEN

- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_model_eval_authorization.py` 退出 1，7 failed；首错为 `AipModelRuntimeResolver` 缺 `preflight_model_evaluation`。
- GREEN：同文件 7 passed；扩充错 head/hash/tenant、Provider/Price/hash/治理/健康及 `executionAllowed=True`/业务用途拒绝后，五文件相邻回归 `49 passed, 7 warnings`，退出 0：`tests/aip/test_model_eval_authorization.py`、`test_aip_model_runtime_resolver.py`、`test_model_resolver_connection_scope.py`、`test_aip_model_runtime_contracts.py`、`test_aip7_model_runtime_store.py`。`py_compile`、`git diff --check` 退出 0；ruff 在仓库 venv 不可用。

## 方案一致性及风险复审

只增加独立 `ModelEvalPreflight` 与 resolver 的 read-only 专用入口，原 `resolve`、普通 active+Gate 门、`AipExactProviderInvoker` 均未改。当前 exact 候选/head 失配抛拒绝；模型、Provider、Price、治理、健康依赖产生 blocker；无论依赖结果如何，预检固定 `purpose=quality-eval`、`executionAllowed=false`，且持续含批准、预算容量、transport 未核阻断。没有 Secret、Provider 调用、EvalRun 或 Gate 写入。

风险：`list_eval_candidates` 与各依赖读取可跨事务；本对象刻意不能作为执行令牌。GT-b 必须在原批准/发送意图事务中重验当前 head、来源 hash、Provider/Price/政策/费用与撤销。测试 fake 只证明合同与 fail-closed 分支；PG 相邻测试不等于当前客户正式授权。浏览器无变更不适用。当前真库 a0v118 只读、代码头132，Host/worker/Provider 未启，自然首链和今日最新栈重启均未完成。
