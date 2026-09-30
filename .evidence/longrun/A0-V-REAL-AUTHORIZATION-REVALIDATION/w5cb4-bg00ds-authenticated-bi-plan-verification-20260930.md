# W5CB4 BG00ds｜认证 actor 的 signed-approved BI Plan draft 入口验证

## 施工边界

复习 231、231-3、231-9 及 BG00dr 文件级方案后，新增 `POST /v1/aip/production-contracts/responsibility-plans/bi-preparation`：请求仅安装 ID、强 `If-Match` 和 `Idempotency-Key`；服务端 actor 仅取已认证 Principal，拒绝 dev token。事务内顺序为 tenant scope→安装 ETag/行锁→`CurrentControlPermission` 的持久成员/角色/marking→唯一 signed-approved BI 模板→六个 active AgentInstance 版本 `FOR SHARE`→Plan draft 与独立 operation Receipt→commit。`request_context` 哈希包含 actor、安装 ETag 和模板 exact ref；相同 key 异目标拒绝。原通用 Plan 创建改为复用同一内部事务原语，其已有 `responsibility_plan.create` 操作及 body 哈希不变。历史物料化/就绪方法去掉默认开发 actor。

只创建 draft Plan，不创建 Stage、不冻结、不配置 binding、不启用 Host/worker/Provider、不产生业务 Run；八候选中的 `responsibility_plans` 仍要求 frozen head，故此代码不消除当前缺候选。当前真库只读，本波没有调用新写入口。单元测试中的测试 actor/连接替身只证明控制流，不是正式业务验收。

| 检查 | 命令/范围 | 退出码与结果 |
| --- | --- | --- |
| RED | `python -m pytest -q ...::test_signed_bi_plan_preparation_rejects_dev_identity_before_database_access` | 1；`ImportError: SignedBIPlanPreparationService`，证明入口缺失。 |
| 身份与事务顺序 | 同测试 + `test_signed_bi_plan_preparation_orders_current_checks_before_one_receipt` | 0；2 passed；dev 在连接前拒绝，正向单测顺序及单次 commit 满足预期。正向为单测替身。 |
| 路由合同 | `test_signed_bi_plan_route_uses_principal_and_strong_installation_etag` | 0；1 passed；`If-Match: "3"` 传递当前 principal，弱 ETag 400，body 任意 actor 字段拒绝。 |
| 相邻累计 | `python -m pytest -q` 指定 BI 模板/角色/物料化/就绪与 W2A/W2B Store 六文件 | 0；87 passed；通用 Plan 路径相邻回归通过。 |
| 装配/静态 | `AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api ... python` 读取 `app.openapi()`；`python -m py_compile`、`git diff --check` | 0；新 POST 路由存在、响应 201/422；编译与差异检查通过。OpenAPI `security` 元数据为空，沿用项目 `require_principal` header dependency；正式安全由运行时与 DB 当前权限双门决定。 |

## 复审与保留风险

`AipProductionContractStore` 旧通用操作与 hash 保持一致；新 dedicated operation `bi_responsibility_plan.prepare` 与它分离。安装行锁覆盖直到同事务 Plan/Receipt 提交，权限在锁后复核；签名解析器会再次在 Store 依赖检查时复验。当前缺 OIDC 当前成员、正式 growth1.12 安装和六合法实例，不可用伪造 OIDC Principal 或脚本开发 actor 做实际写入验收。尚缺真实 PG 正向/并发撤权、HTTP 正向、产品 UI 与浏览器截图；这些必须由独立 test-only 合法身份链和之后正式当前授权补证。下一波先核验 test-only 可用的合法身份/Receipt 来源，若不足只做负向与 UI 阻断接线；不得借 mock 计作正向。
