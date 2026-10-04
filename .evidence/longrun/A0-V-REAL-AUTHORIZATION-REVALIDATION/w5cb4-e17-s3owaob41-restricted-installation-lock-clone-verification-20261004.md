# E17-s3o-w-ao-b41｜隔离受限安装锁函数验证

## 方案与实现复审

- 方案 `m1@6330e7ab` 复习 231-3、BIND-1 和既有 test-only BI Plan `SECURITY DEFINER` 安装锁模式。只在既有 disposable full-schema PG/OCI 的 Growth1.13 test-only 签名 active 安装增加测试；不添加生产函数、Alembic 迁移、正式角色或当前卷写入。
- 随机非 owner/非 runtime role 保留 b39 的八表 SELECT、四租户 RLS，绝不授安装表 UPDATE。test-only 函数是独立随机名称，`SECURITY DEFINER SET search_path=pg_catalog`，调用只接受精确 session_user、org/project GUC、SERIALIZABLE 可写事务、安装 id/ETag、active=current 且 revision active；锁 `bundle_installation` 行 `FOR SHARE`，返回 pk。PUBLIC EXECUTE 撤销，仅本次 role 获得 EXECUTE。finally 删除函数、policy、role 并查角色/函数都不存在。
- 该函数仅证明低权调用可以通过窄入口持有行锁。SECURITY DEFINER 本身仍需正式迁移 owner/ACL/审计与真实授权链复核；本波没有把它接入生产 Reader/Capability active。

## RED、专项与相邻验证

| 命令/步骤 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`，函数尚未建立 | 退出1，`UndefinedFunction: public.aos_e17_install_lock_…`，目标 RED |
| 同命令，创建函数并 REVOKE PUBLIC、尚未 GRANT 本次 role | 受限调用 `InsufficientPrivilege`，测试断言通过 |
| 同命令，精确 GRANT EXECUTE、补全负例后 | 退出0，1 passed、7 warnings。正向锁函数持有安装行锁；竞争 `FOR UPDATE` 与 Registry advisory `(228,1)` 都在250ms超时，事务结束后均能取得。无 GUC、错租户、错 id、错 ETag、直接 UPDATE 均拒绝；函数/角色 cleanup 后不存在 |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | 退出0，32 passed、2 strict xfailed、7 warnings |
| `py_compile` 目标测试、`git diff --check`、生产 Reader 相对 HEAD 的 diff | 前两项退出0，生产 Reader 无差异 |

## 未闭合门

- 测试函数不等于正式发行身份、正式函数或当前库迁移。正式 `aos_aip_capability_issuer`/Reader/OIDC/Owner仍缺；当前 Installation approved3/active NULL、八配置/六 Binding/Host assignment0、自然首链未完成。Host/worker/Provider继续关闭。
- 下一波先设计受控最小迁移与生产调用合同：函数 owner 与 EXECUTE/默认 PUBLIC 撤销、原租户 RLS/ETag、事务时限、安装行锁→Registry advisory 顺序、原 transition 撤销/换代并发、Binding CAS/Receipt 同事务。当前卷若切换，需要新一致全备、全恢复克隆和零执行窗口；b34/b37 strict xfail 不消除。
