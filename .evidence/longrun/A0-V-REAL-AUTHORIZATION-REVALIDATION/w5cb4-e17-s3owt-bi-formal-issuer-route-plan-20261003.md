# s3o-w-t 第一切片｜BI 正式发行入口禁共享身份

## 事实与上位合同

- 231-3 要求安装/Plan 当前权限同事务复核；231-9 要求六同事实例引用现有 AgentInstance。上一波仅在原签名全 schema 一次性库以独立非 owner 登录证明原 Plan/Receipt。当前真实库的 `aos_bi_plan_issuer` 角色和四个 test-only 函数均为0；当前 API 以 `aos_app` 连接，`db.connect(scope)` 会 `SET LOCAL ROLE aos_runtime`，无法成为独立 BI 发行者。
- `routers/aip_production_contracts.py` 仍把公开 `bi-preparation` 和 `bi-preparation/rebind` 依赖解析为模块级默认服务，它们使用同一 API 数据库连接。即使将来签名/六 Agent 到位，这条 HTTP 写入口也不能以 API 共享身份冒充正式发行。
- 当前 API LaunchAgent 没有外部 OIDC 配置项，独立发行进程/受保护凭据来源也未建立。可自设 `aos.actor` 或租户 GUC 不能代替外部 JWT 认证或 OS 隔离。

## 文件级步骤

1. `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py`：RED 断言默认 HTTP 依赖不得直接返回同 UID/同 DB 的写服务；请求注入专用测试服务仍保留路由参数、强 ETag 和 Principal 合同测试，不把 Spy 视作正式验收。
2. `services/aos-api/aos_api/routers/aip_production_contracts.py`：仅将默认 BI prepare/rebind 写依赖改为明确 `BI_FORMAL_ISSUER_REQUIRED` 503；保留只读 admission/Receipt 路由及其它生产合同入口。该依赖未来只能由经外部 OIDC 重验、独立 OS UID/私有 IPC、精确 DB issuer 凭据的正式服务替换；不得以环境开关直接返回旧共享 DB 服务。
3. 专项与相邻回归、`py_compile`、diff 审查；当前 HTTP 未授权写无副作用，原签名一次性库事务仍可作为独立 SQL 证明。适用时浏览器/HTTP 验证页面继续禁入。

## 后续正式迁移与恢复顺序

- 先独立发行进程/受保护凭据和 JWT 每请求重验，限制固定 org-org/dev-project、强 ETag/幂等、同事务原签名安装与 Plan/Receipt；再在可销毁全备克隆把四函数和精确 ACL/owner 落为 migration，并证明错 caller、错租户、任意六 ID、撤权并发、未知响应只读对账、回滚/恢复。完成新一致备份、全链克隆与零执行窗口后才考虑当前库迁移。
- 本切片只关当前 HTTP 共享身份捷径，不创建正式凭据/角色，不写当前库、不启 Host/worker/Provider；不能把 503 或隔离测试当正式首链。
