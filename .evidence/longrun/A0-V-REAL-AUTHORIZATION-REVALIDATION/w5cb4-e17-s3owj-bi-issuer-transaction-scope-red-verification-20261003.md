# E17 s3o-w-j BI Plan 独立发行者首个拒绝点

基线 `aos-platform/m1@04b08977`、Authority `AOS-001218`。先读 231/栖月汇/D-wave、原 `SignedBIPlanPreparationService.prepare`、`apply_asset_transaction_scope`/`apply_transaction_scope`，再落 s3owj 文件级计划和隔离测试。未改生产代码/迁移/UI，当前权威库只读。

| 验证 | 输出 |
|---|---|
| 原事务次序 | `ecommerce_business_investigation_aip_authority.py:prepare` 同一连接先调用 `apply_asset_transaction_scope`，后安装 `FOR UPDATE`、权限/成员 `FOR SHARE`，最后原 Plan Store 写 head/revision/Receipt。`tenant_transaction.py` 对已采纳 TI6 policy 的非 runtime/aos_app 登录调用 `tenant_scope.py:apply_transaction_scope`；其第一句 `SET LOCAL ROLE aos_runtime`。 |
| 独立身份 RED | 已签名 Growth1.13 隔离安装下，前波非 owner `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS` Plan issuer 真实登录；`pg_has_role(...,'aos_runtime','member')=false`。调用原 `SignedBIPlanPreparationService.prepare`，首个 SQL 以 `psycopg.errors.InsufficientPrivilege`（role）失败；Plan head 与 `bi_responsibility_plan.prepare` Receipt 均零增量，rollback 后原 generic Plan Store 与原 BI 全链仍通过。该拒绝是预期失败封闭，不是 BI prepare 正向。 |
| 专项与相邻 | `AOS_DATABASE_URL=<当前18435集群仅用于创建一次性库> AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=<本地回执> .venv/bin/python -m pytest -q --tb=short tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` → `1 passed`、exit0；Plan/Receipt/W2B 相邻 `28 passed`、exit0；`py_compile` exit0。 |
| 残留/真库 | 只读查询当前 `aos_current_preview_20260927@a0v_135`：正租户 Plan head0、共享 Receipt0，临时 `s3owi_plan_%` 角色0、`aos_test_%_ti4_test` 数据库0；隔离 OCI owner 容器0。当前 Host/worker/Provider 未启。 |

复审：简单授予 Plan issuer `aos_runtime` 成员身份会破坏独立发行者和前波 runtime SELECT-only 目标，不能视为修复。BI prepare 的正式独立事务身份语义、安装锁/权限读取 ACL 与 Plan 写入同事务边界需单独设计、测试、迁移；当前仅确认最先拒绝点。下一项先做 successor/Content 原写者的独立正反切片，不因 BI 路径缺正式接线停长期 Goal。test-only Growth1.13/AgentInstance 不是当前正式安装或首链证明。
