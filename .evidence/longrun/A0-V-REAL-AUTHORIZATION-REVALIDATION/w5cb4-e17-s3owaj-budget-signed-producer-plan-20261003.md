# E17-s3o-w-aj：正式预算生产路径与 Binding 只读门联测

## 上位方案和现状

`231-9` 要求首链预算通过；BIND-1 §5 要求同租户 exact Budget 证据。s3o-w-ai 已修复 Binding 对当前 active BudgetPolicy 的只读核验，并在原卷完成最新栈禁入复验。当前真库 Provider/Route/预算/Binding 仍为空。

既有 `test_budget_cost_configuration_pg.py` 在可销毁 PG 中使用原受限发行、双人批准、消费与 `aip_configure_budget_cost_a0v_128` 产生配对 Price/BudgetPolicy；它保留 `activationEligible=false`，可用来检查真实表形状和来源，而不造当前正式实例。

## 本切片文件级计划

1. 只改 `services/aos-api/tests/aip/test_budget_cost_configuration_pg.py`：复用该文件的 `approved→consume→derive` 原合同，让 `PostgresBindingDependencyAuthority` 通过 read-only scoped 连接查新发行的 exact BudgetPolicy；正租户有效时 true，`dev-org` false，窗口到期 false，head 漂移 false。测试不得直接写当前库或使用假模型路线宣称 Binding 可激活。
2. 首次运行作为实际集成 RED/验证；如果是受限 reader 权限或查询形状失败，依据 SQLSTATE 与方案做最小修复，再跑本测试及相邻预算配置与 Binding 专项。
3. 对照原 `AipModelGovernancePolicyStore.require_exact_active` 和 Route resolver：它还校验 BudgetRevision 及模型治理。本波只证新增只读预算 head 门与正式生产行相容，不替代 Route/Provider/Eval 全链。

验收：隔离库无跨租户可见或误放行，现时真实库只读且 Host/worker/Provider 关闭；记录结果与后续来源顺序。
