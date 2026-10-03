# E17-s3o-w-ao-b27｜同版本 Capability Receipt 一一配对文件级方案

## 上位与现时门

- 231-4 单库权威、专用非 owner、FORCE RLS、受控列/谓词及串行迁移；BIND-1 31 要求租户 CAS、幂等与 Receipt。b25/b26 在完整恢复及 disposable PG 均已证明仅靠行形状不足，生产库/代码头仍 `a0v_135`，当前写503。正式私有 issuer/OIDC/Owner/Host未齐；当前库只读。
- `aip6_002` 只对 `(org,project,operation,idempotency_key)` 唯一；b24/b26 test-only deferred 守卫只用 `EXISTS`，尚未证明同一 Binding 版本/事务只有一张 Receipt。重复不同 idempotency_key 的同 operation Receipt 可能都满足 `EXISTS`，影响幂等审计。

## 文件级步骤

1. 只改 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable PG test-only 证明：合法 evaluate 更新后插两张不同键但相同 `(tenant,binding,version,operation)` 的 Receipt，要求拒绝；先记录 `DID NOT RAISE` RED。再用单个合法 Receipt、普通 Agent/Skill/Run/Handoff 操作和原负例证明兼容。
2. 最小修订 test-only Receipt deferred 守卫与 Binding deferred 守卫：对当前事务同租户、同 Binding、同 version 的 Capability Receipt 计数必须精确等于1；其他共享 operation 不进入该计数约束。即使另一个 operation 或逆序写，也不能成第二张。不得用可写 session GUC 宣称命令权威。
3. 目标专项与 b24 相邻五文件回归，静态检查、方案/代码复审、verification，m1 精确提交并更新01/06/D-waves/Prime。此波不新增正式迁移、不放宽 `RegistryIssuerConnectionFactory.runtime_insert`，不动当前权威库；下一波继续正式受控 operation 来源与列白名单、历史行/回滚。

禁止：dev-org正向、商城源读取、旧12Run重放、手工run_definition、230 L0、Host/worker/Provider无授权启动、push或清理旧库/卷/备份。
