# E17-s3o-w-ao-b11｜EvalGate target 与 Binding exact 关系负审计

## 方案与文件级检查

- 上位 BIND-1 31 第 235–241 行要求 Capability published exact、Route→Model→Provider→Policy/EvalGate exact，所需 gate 必须 passed；当前 D-wave b11 只授权查确切错 target 路径，有证据后才最小修复。
- 精确核对 `services/aos-api/aos_api/aip_binding_readiness_service.py`、`aip_model_runtime_resolver.py`、`aip_eval_authority_store.py` 与两份目标测试。原 binding 先要求 `route_revision.eval_gate_ref == dependencies.eval_gate_ref`，又要求 `route_resolution.route == dependencies.model_route_ref` 且 readiness READY；resolver 对 route 和 selected model 分别调用 `require_exact_passed(... expected_target=evaluation_candidate_ref(...))`，canonical authority 逐项比 target 类型/id/revision/hash。
- 这一传递链已拒绝错 target；没有发现可复现的独立错 target 接受路径。为避免重复 authority 与协议漂移，本波不改生产代码、不造 RED、不新增重复测试；候选缺陷登记为未成立。

## 验证与边界

- `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_model_runtime_resolver.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py`：34 passed、7 既有 warnings、exit0。该测试仅验证现有代码合同，不证明当前正式 gate 存在。
- b10 当前栈已在 `m1@e25cc962` 用原卷135重启，原库只读 EvalGate/Binding/Host0；本波无代码/迁移/API/UI/DB 变更，因此无需再次重启或浏览器验收。当前缺正式 Model/Route/Eval/Owner、八配置/六 Binding 和自然首链，Host/worker/Provider关。
- 下一波回到已登记 ToolBinding 正式 signed source、独立 issuer、同事务 RegistryReceipt/收权；当前四签名 bundle 无 ToolDefinition，不能造当前正向。可独立推进 BI 安装锁的隔离合同，不扩大权限或写当前库。
