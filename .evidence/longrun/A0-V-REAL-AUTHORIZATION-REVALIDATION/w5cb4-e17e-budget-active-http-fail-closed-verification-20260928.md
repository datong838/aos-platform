# W5CB4 E17-e｜预算 active HTTP 失败封闭验证（2026-09-28）

## 方案/代码复核

- 对照同目录 `w5cb4-e17e-budget-active-http-fail-closed-plan-20260928.md`，仅改 `routers/aip_budgets.py` 与对应 API 测试。公开 POST 在调用 Store 前拒绝 `BudgetLifecycle.ACTIVE`，返回 422 `AIP_BUDGET_ACTIVE_APPROVAL_REQUIRED`；draft 仍走原 principal/tenant、幂等键、If-Match、Store 和 GET 路径。
- 未改 BudgetRevision 合同、内部 Store、PG schema、安装候选读回、Host/worker 或 Provider。当前库只读。本波是 HTTP 暴露面的禁入切片，内部 Store 可在隔离测试中构造 active，不能扩大宣称为全路径批准闭环。

## 测试证据

| 项目 | 新鲜命令/结果 |
| --- | --- |
| RED | `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_budget_api.py -q`：退出 1，新增 active 负例实际 201 而预期 422；2 passed、1 failed。系统 `python3 -m pytest` 首次因非项目 venv 的 Alembic 导入错误退出 4，不计 RED。 |
| GREEN/相关累计 | `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_budget_api.py services/aos-api/tests/aip/test_aip_budget_contracts.py services/aos-api/tests/aip/test_aip_model_governance_policy_api.py -q`：退出 0，14 passed。 |
| 静态差异 | `git diff --check`：退出 0；差异仅预算路由和对应测试。`ruff` 当前项目 venv 无模块、PATH 无命令，因此未声称 lint 通过。 |

## 未完成

- 正式 Approval Owner/精确批准事件、金额/窗口/maker-checker 绑定与 active 正向产品流程尚未接线；八类当前有效候选仍为 0，不能启 Host 或称业务首链通过。
- 该 API 运行进程若未在提交后重启，线上本地 8080 仍可能是旧代码；须使用当前权威卷与受保护签名 Receipt 重新预检/启动并只读验证。浏览器 `browser-pilot` 无可调用能力，新鲜截图待补。
