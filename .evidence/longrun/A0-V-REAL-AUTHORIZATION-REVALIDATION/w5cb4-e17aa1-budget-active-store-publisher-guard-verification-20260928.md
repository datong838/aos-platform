# W5CB4 E17-aa1 预算 active 通用 Store 发布入口禁入验证

## 基线与方案

`m1@5f44f830`、authority `AOS-000841`，当前权威库 `aos_current_preview_20260927@a0v_110`。复习 231-3/5/9 与 E17-aa 文件级方案后，审计 `AipBudgetAuthorityStore.publish`、HTTP active 422 及两个历史直接发布脚本。当前仅一名正式 owner；预算 Head/Revision/activation 证据均 0，未创建真实批准或预算。

## RED / GREEN

- 新增 `test_aip_budget_store.py` active 首版/换版负例；RED 因缺 `BudgetActivationApprovalRequired` 收集退出 2。最小实现是在通用 Store 任何事务前拒绝 `BudgetLifecycle.ACTIVE`，Draft 的既有 CAS/幂等/租户隔离保持。
- 首次 GREEN 运行暴露测试共用预算 ID，已改独立 ID，避免把前一测试留下的 Draft 当本次拒绝副作用。Store 2 passed、退出 0。
- 两个旧治理正向测试原用通用 Store 直接制造 active，邻接初测 2 failed/5 passed；改为 `tests/aip/_budget_test_fixture.py`，只在名称匹配 `aos_test_*_ti4_test` 的可销毁 PG 中造历史 active 行以验证下游读链，不提供生产绕过入口，也不算正式审批。复测 9 passed、退出 0。
- 累计预算 Store/API/activation/治理、旧脚本负例 30 passed、退出 0；`compileall -q`、`git diff --check` 退出 0。`ruff` 可执行文件在项目虚拟环境不存在（退出 127），未把它记为通过。

## 代码复审与风险

- 生产代码中 `aip_budget_revision` 的 INSERT 和 Head UPDATE 只在 `AipBudgetAuthorityStore.publish` 找到；直接调用通用 Store active 现拒绝且不写 Head/Receipt。公开 HTTP active 422 未改变；历史 `bootstrap_r1_runtime_authority.py` 有旧库身份硬门，当前 `a0v_current_runtime_configuration_authority.py` 也限定隔离库。此波没有运行这些写脚本。
- 此门只覆盖应用 Store；数据库运行角色仍有旧表写权限，正式原子消费和 DB 级单次约束、外部费用上界仍未实现。当前租户无独立 checker，不可启 Host/worker、不可称预算激活或自然首链完成。
- 本波无迁移、无当前库写、无商城源读取、无 `dev-org` 写、无旧 Run 回放或手工 Run。浏览器页面逻辑未改，browser-pilot 不可用，无新增截图。
