# W5CB4 BG00du｜认证 BI Plan 事务负向与回滚验证

## 范围与证据

按 BG00du 文件级方案执行，新增测试只在 `tests/conftest.py` 创建并销毁的隔离 PostgreSQL 中写测试行；测试注入的模板解析器、测试 actor 和 AgentInstance 只用于数据库原语反证，不计正式来源或业务验收。当前库/clone 全程只读，Host/worker/Provider 关闭。

| 项目 | 命令/结果 |
| --- | --- |
| 事务回滚、幂等 | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py::test_bi_plan_later_failure_rolls_back_draft_receipt_in_isolated_pg --disable-warnings --tb=short` → exit 0，1 passed。同事务写 draft Plan+Receipt 后，同 key 同目标回读原 `plan_id`，异安装上下文复用 key 抛 `ProductionContractIdempotencyConflict`；随后强制失败，下一只读事务确认该 key 的 Receipt=0、测试 actor 的 Plan revision=0。 |
| 身份边界 | 新增 `test_signed_bi_plan_preparation_rejects_cross_tenant_oidc_before_database_access`；错租户 OIDC 在连接前 `PermissionError`，不触发数据库。既有 dev token 在连接前拒绝仍保留。 |
| 相邻回归 | `services/aos-api/.venv/bin/python -m pytest -q` 指定 BI 模板、角色、物料化、就绪与 W2A/W2B Store 六文件 → exit 0，`89 passed`；`git diff --check`、`py_compile` → exit 0。无生产代码更改。 |
| 当前/clone 只读复核 | 使用两个固定 connection helper，连接后 `conn.read_only=True`，精确查询 `org-org/dev-project` 的 `aip_production_contract_receipt.operation='bi_responsibility_plan.prepare'` → exit 0；当前 0，clone 0。 |

## 方案一致性与剩余风险

隔离 PG 证明 Store 事务的原子回滚和 idempotency context hash；身份测试证明无效租户/开发 token 的前置拒绝。尚未证明真实 OIDC actor 对已签名 approved 安装的产品 HTTP 正向、并发撤权或六实例当前可用。BG00dt 证实两库六实例均 `provisioning=6/active=0`，当前无 growth1.12，故没有合法正向前提。本波不修改数据或凭据以绕过该缺口；下一波转产品 UI 的精确禁入/缺口呈现，并继续正式来源审计。
