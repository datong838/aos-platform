# E17-s3o-w-ai：CapabilityBinding 预算 exact 就绪门

## 上位方案与现场

- `231-9` 首链规定预算/审批通过后才可产生模型产物；`AIP-BIND-1` §5 第 6 项要求 Budget 证据存在、同租户且允许，激活时重算快照。
- 当前 `org-org/dev-project` 的 ProviderInstance/ModelRoute/RuntimePolicy/ReleaseGate/EvalContract/EvidenceBundle/ToolBinding/BudgetRevision/CapabilityBinding 正式行均为 0。`strategy.plan` 空依赖只读预检为 BLOCKED，含七个缺失原因；本波不会制造正式来源或激活六实例。
- 代码 `aip_binding_readiness_service.py` 仅比对 `RuntimePolicyRevision.budget_policy_ref` 与请求引用，未读预算权威本身；因此若路线其余条件 READY、策略指向一个不存在或过期的预算引用，就绪可误报 AVAILABLE。已有受限 reader 白名单含 `aip_model_governance_policy_head/revision`。

## 文件级方案（先 RED 后最小实现）

1. `services/aos-api/tests/aip/test_aip_binding_readiness_service.py`：加预算权威缺失/过期/非当前修订失败关闭与正常 exact 通过测试。假 Authority 必须显式给预算判断；不靠现有 `ModelStore` 假对象冒充数据库权威。
2. `services/aos-api/aos_api/aip_binding_readiness_service.py`：在现有 `BindingDependencyAuthority` 与 PG 实现加只读 `budget_policy_available(scope, ref, evaluated_at)`；同租户、kind=budget、head.current_revision、revision、hash、active 生命周期和 `[effective_from,effective_until)` 同时满足才通过。原缺失原因 `BUDGET_POLICY_MISSING` 不改合同。仅在运行策略的 exact 预算引用已匹配后查权威。
3. 回归：专项与受影响的 Binding/reader 测试；检查差异与方案一致。PG 当前库只读，不改 schema、配置、Host/worker/Provider，不创建测试身份进入正式库。现有 test-only 隔离 PG 如需要另行证明。

## 验收边界

RED 应展示伪策略引用可以让现代码误报 AVAILABLE。修复后该引用 BLOCKED；exact active 当前修订且在有效期内仍 AVAILABLE。此代码门不算当前实例八配置、六绑定或首链正向；正式发行来源/Owner 仍另波处理。
