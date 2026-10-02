# E17-s3g 原签名预算候选读者联测验证

- 基线 `m1@7a47d37b`、Authority `AOS-001176`。复习 231 首链预算边界、栖月汇真实动作方案、E17-f/BG00ga 和原 Store/SQL：普通 active Budget/Quota/BudgetPolicy publish 被拒；正式 BudgetCostIssuer→低权 consume→`aip_configure_budget_cost_a0v_128` 可在隔离库派生 BudgetPolicy/Price，`activationEligible=false`。
- 文件级变更仅 `services/aos-api/tests/aip/test_budget_cost_configuration_pg.py`。先 RED：把基线错误设在签名提案前，测试回 `data_policies`、`egress_policies` 也 +1，退出1。查明签名提案准备会创建这些合法前置来源，将基线改为提案后、预算消费前；未修改产品逻辑或绕过任何门。
- `services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/aip/test_budget_cost_configuration_pg.py services/aos-api/tests/aip/test_budget_configuration_runtime_pg.py services/aos-api/tests/extension_runtime/test_runtime_configuration_candidates.py`：24 passed，退出0。新测试确认原签名审批后，低权 Budget 消费与派生使 `budgets`、`budget_policies` 各+1，其他六项不变；dev-org 计数不变；派生 Receipt 仍 `activationEligible=false`。`py_compile`、`git diff --check` 均退出0。
- 与方案一致性：仅证明原预算链在一次性全迁移隔离库通向运行配置候选读者；不证明当前实例八候选齐备或价格可用、Quota 正式来源、绑定、Host 或自然首链。当前真库未写，Host/worker/Provider仍关。下一波核原 Quota 独立签名激活，再查 RuntimePolicy/ResponsibilityPlan 合法来源。
