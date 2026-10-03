# s3o-w-o 第一切片｜安装只锁 CAS 隔离证明

- 基线：`m1@8c79066e`，当前权威库只读，PG/API/Web 仍为 15:32 最新栈；本波未改生产代码、迁移、角色或当前卷。
- 原约束：`PostgresInstallationStore.lock_for_cas` 和 `lock_for_transition_in_transaction` 用 `FOR UPDATE`；安装状态 writer 最终 `UPDATE bundle_installation`。231-3 要求安装头先锁、ETag/批准精确、同事务提交。PostgreSQL 18 SELECT 文档明确任一行锁子句要求 UPDATE 权限。只读发行者不应获得 UPDATE。
- 方案：`w5cb4-e17-s3owo-installation-cas-plan-20261003.md`。一次性 PG schema 中，非 owner/NOINHERIT/NOSUPERUSER/NOBYPASSRLS BI login 仅获安装表 SELECT+租户 RLS；SECURITY DEFINER 函数固定 search_path/表名、`session_user`、事务 GUC/目标租户和 ETag，只返回 ETag 并持原安装行锁到事务结束；`PUBLIC` EXECUTE 撤销。无正式 migration/当前库安装。
- RED/诊断：首次在 `tests/asset_registry/` 收集失败，因跨目录 fixture 不可导入；移到既有 `extension_runtime` PG fixture 后首测因测试角色清理遗漏失败，已修复。最终测试中直接 `FOR SHARE` SQLSTATE42501、直接 UPDATE SQLSTATE42501；不是业务 RED 的伪造成功。
- GREEN：`AOS_EXTENSION_PG_TEST=1 .venv/bin/python -m pytest -q --tb=short --disable-warnings -o log_cli=false tests/extension_runtime/test_e17_s3owo_installation_read_lock_pg.py tests/extension_runtime/test_plan_readonly_lock_protocol_pg.py tests/asset_registry/test_e17_s3own_bi_issuer_scope_pg.py` → `3 passed, 7 warnings`、exit0；错租户/错 ETag/冒用 caller 拒绝，正向原 writer 改版等待超时，释放后改版成功，旧 ETag 再拒绝。角色/函数/策略/临时 schema 由测试清理。`python3 -m py_compile` 与 `git diff --check` exit0。
- 复审：证明的是隔离 SQL 锁协议，尚未接原 `SignedBIPlanPreparationService` 的 prepare/rebind/freeze、正式 SELECT ACL/凭据/签名/六 Agent、Migration 克隆与当前库零执行切换。首链、配置、Host 均不因本探针变 GREEN。下一波先在原全 schema 克隆验证函数与原 Store 的共同事务，检查所有 BI 前置表权限及并发安装变更，再写生产 migration/接线方案。
