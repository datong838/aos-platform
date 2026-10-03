# E17 s3o-w-j：BI Plan 受限发行事务身份调查计划

基线 `aos-platform/m1@04b08977`、Authority `AOS-001218`，前波隔离签名 Growth1.13 + 原 generic Plan Store 受限登录 GREEN，当前真库仍只读135。按 231-3/4/5/9、栖月汇方案及 D-wave s3o-w-j，仅调查 BI 服务原事务身份第一拒绝点；不改架构或当前实例权限。

## 文件级 RED

- 读原 `SignedBIPlanPreparationService.prepare`：同一连接先 `apply_asset_transaction_scope`，再安装 `FOR UPDATE`/成员与权限 `FOR SHARE`，最后原 Plan Store in-transaction 写 head/revision/Receipt。`apply_asset_transaction_scope` 对独立非 `aos_app`/`aos_runtime` 登录、已采纳 TI6 policy 时调用 `apply_transaction_scope` 的 `SET LOCAL ROLE aos_runtime`。独立 Plan issuer 不属于 runtime 时应在此处 fail-closed；若简单赋予 runtime 成员身份，会破坏前波独立写者最小权语义。
- 最小测试文件：`services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py` 在已签名的隔离安装实例内直接调用原 BI prepare 的独立 Plan LOGIN，断言实际 SQL 权限拒绝、Plan/Receipt 零增量；`test_growth_signed_installation_full_schema_pg.py` 仅传原安装 etag。必须保留后续原全链测试 GREEN。
- 根据 RED 输出再判定可行的最小接线：只有正式 issuer/ACL 与事务作用域语义可自洽时才写生产代码；否则保留该 BI 路径失败封闭并转测不依赖它的 successor/Content 独立写者。不得给 Plan issuer 继承 runtime、`SET ROLE aos_runtime` 绕过身份、手插当前正式配置。

验证：原隔离 Growth1.13 整测、相邻 Plan/Receipt 测试、角色/一次性库/OCI 清理、当前真库只读回读。前波签名树/实例均为 test-only，不构成当前正式身份与首链。
