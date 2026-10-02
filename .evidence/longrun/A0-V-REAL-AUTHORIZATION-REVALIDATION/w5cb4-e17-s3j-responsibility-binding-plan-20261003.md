# E17-s3j 原职责绑定与冻结：文件级核查方案

基线：`m1@0f415ea2`，Authority `AOS-001179`，真库 `aos_current_preview_20260927@a0v_135` 只读。目标是确定原 signed Growth 安装到 frozen ResponsibilityPlan 的首个合法缺口；不以手插 active SkillBinding、假 readiness 或直接构造冻结 Receipt 代替原生产者。

## 上位与现有实现

- 231 主计划、E17 BI Plan 冻结 D-wave 要求六职责从已发布 Skill、active SkillBinding、CapabilityBinding、原 readiness 及精确安装/rebind Receipt 到同事务冻结；当前实例 Host/worker/Provider 关闭。
- `aip_production_contract_store.py:_responsibility_blockers` 在冻结前检查每个 assignee 的 active SkillBinding 与 CapabilityBinding；缺一项报 `SKILL_BINDING_NOT_ACTIVE`。
- `test_growth_signed_installation_full_schema_pg.py` 已有原签名 Growth1.13 安装→rebind→freeze 负例：六职责缺 active SkillBinding 时 Plan head 未推进、freeze Receipt 为零。六 AgentInstance 为隔离直接插入，仅能用于负例。
- `test_aip_agent_registry_store.py` 的绑定正例使用 `insert_governed_published_skill_fixture` 和 `_ReadySkillBindingService`，不能证明正式签发/评测来源和真实 readiness；`test_aip_skill_publication_service.py` 的 published Skill 正例仍使用 test-only 签名 Run/Report 及 Route/Policy 夹具。
- 普通预算的原 Task/TaskRun 正例见 `test_content_first_action_budget_pg.py`，其 Action `action_binding_hash=None`，预算预留按原门拒绝。Binding 与预算都不能靠手补字段打通。

## 本波核查与文件

1. 对 `services/aos-api/aos_api/aip_production_contract_store.py`、`aip_agent_registry_store.py`、`aip_skill_binding_readiness_service.py` 和签名 Growth 测试追踪六个 slot 的 exact Skill、capability、budget、route、policy、Eval Gate 依赖，记录第一个真实缺口与原拒绝码。
2. 若现有 signed Growth 测试只断言首个 blocker，先在 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 用隔离 PG 增加最小的六 slot 未绑定/零冻结 Receipt 断言；预期旧代码可 GREEN 时明确记录“补覆盖，无新 RED”，不人为造错。若测试链无法合法生成 active Binding，只保留 RED 及缺口，不改生产门禁。
3. 只在合法原发布、CapabilityBinding 和 readiness 生产者都可接通时，再以 `services/aos-api/tests/aip/test_aip_agent_registry_store.py` 的原 Store API 做同租户正向，错租户/过期/漂移反向，并回到原 signed Growth 冻结。不能复用 `_ReadySkillBindingService` 或手插发布/active 行宣称正向。
4. 专项与相邻回归、方案/代码一致性、租户隔离及 Receipt 行数复核；不涉及前端则浏览器只读回读现有三 blocker，不将页面状态当作 Plan 成功。证据写同目录 verification；D-waves、01/06 与续接文档登记本波实得结果。

退出判据：明确原链是否产生六个 active Binding 与 frozen Plan；失败必须给出精确首缺口、零副作用证据和可独立推进的下波。当前正式首链仍 pending，不能用隔离夹具填平授权。
