# GT-a Model 首评用途准入合同文件级计划

基线 AOS-001082 / `m1@ac022438`，Task `W5CB4-GTA-MODEL-EVAL-ADMISSION-20261002`。上位 BG00GT 方案经用户批准设计、编码、隔离验证；真实 Secret/Provider/Host/当前库迁移仍无批准。复习 231-5、AIP22、BG00GT 与现有 `AipModelRuntimeResolver`、`AipModelRuntimeStore.list_eval_candidates`。

## 1. 当前原 Owner 与不能跳过的门

`list_eval_candidates` 只给 draft/validated 源与 next-active 目标、headVersion，并固定 `executionAllowed=false`；它不是批准。普通 `resolve` 明确要求 route/model active + exact Eval Gate。`AipExactProviderInvoker` 只接受普通 READY，不能把评测候选伪装为 READY。当前没有可核的 Model 首评用途批准 Owner、预算/容量预留或发送意图；因此 GT-a 先增加**无执行权限的精确依赖预检合同**，GT-b 持久批准/费用 Owner 完成前不得返回正向执行许可。

## 2. 本子波精确文件与逻辑

- 新 `services/aos-api/aos_api/aip_model_eval_authorization.py`：定义 `ModelEvalPreflight`，绑定 tenant、源/目标/headVersion、Provider/Price/Quota/Budget 的 exact Ref、检查时刻与 blockerCodes，`purpose='quality-eval'`、`executionAllowed=false` 固定。只读校验对象，不含 Secret 或外部发送能力。
- `services/aos-api/aos_api/aip_model_runtime_resolver.py`：新增专用 `preflight_model_evaluation`，从当前 `list_eval_candidates` 找到唯一 exact Model 候选，回读模型/Provider/Price、治理与健康；不调用或改动普通 `resolve`、`_candidate`、`_gate_passed`。缺失、漂移、非活动 Provider/Price、过期价格、治理阻断、健康缺失一律返回 blocker；所有成功依赖仍带 `eval_approval_missing`，直至 GT-b Owner 真实接入。不得把 callback 注入当作生产批准。
- 新 `services/aos-api/tests/aip/test_model_eval_authorization.py`：先 RED，覆盖候选错 hash/head/tenant、Provider/Price/健康/治理失败，及非质量用途不能被解析；相邻普通 `test_aip_model_runtime_resolver.py` 保持门禁。测试构造只证明预检合同，不宣称当前实例或真实 Provider 可调用。

计划 RED：旧 resolver 无新入口；新测试先失败。GREEN 后专项/相邻回归、`py_compile`、diffcheck；无 UI/真实 Host 改动，浏览器不适用。若当前 Store 方法无法在同一稳定快照回读全部依赖，预检必须保留非授权状态，后续 GT-b 在持久批准事务中重读，不可把本预检对象交给原 Provider transport。

## 3. 后继完整 GT 路线

GT-b 在原 maker/checker 和预算/容量 Owner 上新增 exact 评测批准及发送意图；GT-c 受限 transport、独立执行签名/Usage 与 unknown 对账；GT-d Report/Gate 读证；GT-e Web。只有这整条链与正式实例证据可升级 Model/Route 候选，不凭本预检晋升。当前真库 a0v118 只读、代码头132；不做最新栈重启替代验收。
