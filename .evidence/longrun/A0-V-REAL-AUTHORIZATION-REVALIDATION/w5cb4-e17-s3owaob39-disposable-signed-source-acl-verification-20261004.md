# E17-s3o-w-ao-b39｜隔离签名来源低权 ACL 验证

## 范围与结论

- 方案先行：`m1@4944edc3`。只改既有 Growth1.13 完整迁移、独立 OCI、test-only 签名安装测试；当前 `aos_current_preview_20260927@a0v_135` 不写入，未给正式实例建角色或授权。
- 在 disposable `aos_test_*_ti4_test` 库中，随机非 owner、非 `aos_runtime` 登录无来源 SELECT 时，内部同事务 Reader 确实报 `InsufficientPrivilege: bundle_installation`。随后只授八张来源表 SELECT、四张租户表限定 org/project GUC 的角色 RLS；SERIALIZABLE 调用返回唯一 active/current 签名 Growth1.13 安装与 `EVIDENCE_ONLY_NO_START`，连接可继续查询。
- 错租户及错 content hash 均 `ACTIVE_INSTALLATION_MISSING`；错租户直接 SELECT 安装表为 0，同租户为 1。角色对八表 INSERT/UPDATE/DELETE 均 false，也不是 runtime 成员；finally 精确删四 policy、DROP OWNED/ROLE，并查询 `pg_roles` 证实角色消失。

## 可复核命令与退出码

| 步骤 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`，加 grant 前 | 退出 1，`psycopg.errors.InsufficientPrivilege: permission denied for table bundle_installation`；符合 RED |
| 同命令，精确 SELECT+RLS 后、增加隔离/cleanup 断言后再跑 | 退出 0，1 passed、7 warnings（12.78 s） |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | 退出 0，32 passed、2 xfailed、7 warnings；xfail 为已登记未闭合门 |
| `services/aos-api/.venv/bin/python -m py_compile services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`；`git diff --check -- services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | 均退出 0 |

## 复审与剩余风险

- 方案与实现一致：没有改生产代码、正式 ACL、当前卷或启动门；本波只是验证低权读取所需的八表 SELECT/RLS 可行性。测试中的 test-only Growth1.13 签名不得冒充正式 Registry 发布。
- 低权角色仍无 Binding UPDATE/Receipt INSERT；本波没有安装行 `FOR SHARE`、Registry advisory `(228,1)` 与最终 Binding CAS 的同事务组合，也没有撤销/换代并发 RED。b34/b37 xfail、当前正式 issuer/reader/OIDC/Owner 与八配置、六 Binding、首链缺口保持。Host/worker/Provider 继续关闭。
- 下一波先在 disposable PG 做安装行锁与 Registry 撤销并发 RED，确定最终事务锁序与最小 issuer 权限；当前卷若需迁移，另立备份、全恢复克隆和零执行窗口，不在本波切换。
