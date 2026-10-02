# E17-s3j 原职责冻结依赖核查

基线 `m1@0f415ea2`、Authority `AOS-001179`。本波只审原生产者与禁入，未修改生产代码、测试或真库；因此不宣称新 GREEN 或 frozen Plan 正向。

## 逐点证据

1. 原 signed Growth1.13 安装→active rebind→受控 freeze 测试在 `test_growth_signed_installation_full_schema_pg.py:397-441` 已断言六职责缺 active SkillBinding 时 `SKILL_BINDING_NOT_ACTIVE`、Plan head 不动、`bi_responsibility_plan.freeze` Receipt 为零。该测试需要独立签名 Receipt、OCI 与 disposable PG，本轮未在缺所需环境变量时将 skip 冒充通过。
2. 原 `AipSkillRegistry` 绑定测试 `test_aip_agent_registry_store.py:300-383` 由直接插入的 published Skill fixture 与 `_ReadySkillBindingService` 支撑。它证明 Store 的 create→evaluate→active 状态流，不能证明当前正式签发、真实 Route/Eval Gate、Capability 与预算可用。
3. 原 `AipSkillBindingReadinessService.evaluate` 核 published Skill、PublicationEvent、passed 未过期 Gate、active AgentInstance、active/healthy/fresh CapabilityBinding、ready Route、BudgetPolicy/RuntimePolicy exact refs。当前正式 Model/Route 因首次 Model Eval Owner 缺失仍禁入，故六个真实 active Binding 无合法正向来源。
4. `aip_production_contract_store.py:_responsibility_blockers` 的 agent instance 分支只按 `status='active'` 读取 SkillBinding，再查 CapabilityBinding；未读取 SkillBinding 的 `readiness`、`dependency_snapshot_hash`、`readiness_expires_at` 或 Skill Publication provenance。`bind1_001_operational_bindings.py` 有这些字段，`aip6_001_agent_skill_registry.py` 给 `aos_runtime` INSERT/UPDATE。现有 `test_w2b_production_contract_store.py:303-355` 可直接插入 active、draft SkillBinding 用于负例。**这是需下一波隔离 RED 验证的潜在冻结准入缺口，不据静态阅读宣称可实际越权冻结。**
5. 原普通 Task/TaskRun→Action 审批测试 `test_content_first_action_budget_pg.py` 由 Store 创建真实 Task/Plan/Run，但 `action_binding_hash=None`，预算门拒绝。用 `.venv/bin/python -m pytest -q tests/aip/test_content_first_action_budget_pg.py::test_first_action_uses_public_stores_but_unbound_approval_cannot_reserve -x` 在 conftest 自动创建/销毁的 disposable PG 新鲜复测 **1 passed/7 warnings，exit0**；未把它当作普通/Eval 共桶正向。

## 下一波文件级入口

- E17-s3k：先在 `services/aos-api/tests/test_w2b_production_contract_store.py` 的 disposable PG、`org-org/dev-project` 构造仅用于**负例**的 active 但未评测/已过期 SkillBinding、fresh CapabilityBinding，证明原 Plan 是否误报 ready 或误冻结；不得把手插 binding 当正向来源。若 RED，最小修 `aip_production_contract_store.py` 的职责准入，验证同事务当前 freshness、原 published Skill 与 Receipt 来源；复测 signed Growth 负例及相邻回归。实际可证明的修复范围必须写清。
- 正向仍需正式 Model Eval Owner/签发、active Route、published Skill、六 Skill/Capability Binding 与当前 Growth1.13 身份；Provider 物理容量的正式来源另由 GT-b4b 决定。缺实例授权不阻止上述隔离负例修复。

真库只读；Host/worker/Provider 关闭；未读商城源、未重放旧 Run、未手工 run_definition、未碰 230 L0、未 push。当前八配置、Plan/Binding、Host Owner 和自然首链仍 pending。
