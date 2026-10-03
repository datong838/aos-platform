# s3o-w-w 第一切片 verification｜BI 独立数据库登录门

## 本次可复核执行

- 基线 `m1@3dcdf816`；方案 `w5cb4-e17-s3oww-bi-db-identity-plan-20261003.md` 在代码之前。RED：`.venv/bin/python -m pytest -q -x ... tests/aip/test_aip_bi_plan_issuer_connection.py`，缺 `aip_bi_plan_issuer_connection`，exit 1。
- 最小实现：固定 `aos_bi_plan_issuer` 本机登录、显式库/受保护 passfile；每次连接复查文件和 PG 环境，事务局部双租户绑定；直接核 DB、session/current 角色、无 owner/runtime 成员、非超级/非 BYPASSRLS/NOINHERIT、超时和只读属性。读连接 REPEATABLE READ，写连接 SERIALIZABLE；写后 commit/rollback 重绑定。没有默认连接、凭据输出、网络重试或 HTTP 放行。
- 专项/相邻：`tests/aip/test_aip_bi_plan_issuer_connection.py tests/aip/test_aip_bi_plan_issuer_service.py tests/aip/test_aip_network_issuer_connection.py`，15 passed/2 skipped，exit 0。两个 skipped 是已有 network issuer 额外环境门，非本切片正向证据。
- 原签名 full schema：先用 `scripts/a0v_current_preview_http.py` 的 `preflight` 只读确认当前库 `aos_current_preview_20260927`、原卷连接、库/代码 `a0v_135`、approved 安装、0 runtime binding 和本地签名来源；只把连接参数用于测试夹具新建/销毁 `aos_test_*_ti4_test`，显式 `AOS_EXTENSION_PG_TEST=1`、`AOS_EXTENSION_OCI_TEST=1` 与 Growth1.13 签名回执。`tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 1 passed，exit 0；增量证据包括 test-only 非 owner 发行角色真实 passfile 登录、双租户/只读身份、真实只读事务拒 `CREATE TEMP TABLE`、写连接 rollback 后作用域重绑定。当前真实库未写。
- 方案/代码复审：新连接门不接 API 默认 BI 写口；测试凭据仅存在隔离全 schema 角色窗口。角色若不满足独立登录/权限属性即禁入；不能从测试正向推断当前有正式 IdP、发行 DB 角色/四函数 ACL 或六 active Agent。当前 HTTP 保持503，Host/worker/Provider保持关闭，首链 pending。此次无 Web 改动，浏览器检查不适用；最近原栈浏览器三 blocker 与业务入口0仍是已有证据，非本切片新增验收。

## 下一切片

s3o-w-x：先锁 BI 专用有限私有 Unix 进程及调用权归属，复用内核 peer/不同 OS UID/每请求外部 OIDC/私有目录门；把本连接工厂和 s3o-w-v 至多一次编排显式注入原 Plan 服务/Reader，在隔离克隆证错 peer、错租户、失凭据、未知提交只读对账。正式当前卷 migration/ACL/身份仍单独备份、全链恢复、零执行窗口；缺合法来源时只阻断该实例，继续已登记独立 Tool/配置主线。
