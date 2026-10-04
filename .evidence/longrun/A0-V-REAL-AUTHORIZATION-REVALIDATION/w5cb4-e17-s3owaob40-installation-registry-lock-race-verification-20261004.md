# E17-s3o-w-ao-b40｜安装与 Registry 锁竞争反证

## 方案复审和范围

- 方案 `m1@11399dbe+a6c1b8a1` 先读 231-3/BIND-1、`installation_store.py` 的 `FOR UPDATE/FOR SHARE`、`registry_store.py` 与 `RuntimeReleaseRevalidator` 共享的 advisory `(228,1)`。只在 disposable full-schema PG/OCI、Growth1.13 test-only 签名 active 安装上验证；当前真实库只读，不执行正式撤销/发布或 Host。
- 起初计划给内部 Reader 加默认关闭的安装锁选项；RED `TypeError` 后试做发现低权 SELECT 账号 `FOR SHARE` 报 `InsufficientPrivilege`。给该账号 UPDATE 会突破最小权限，所以未提交的生产改动已撤回，`current_installation_release_evidence.py` 与 HEAD 无差异。本波收口为低权锁权限及竞争窗口的可复现反证，不宣称最终门通过。

## 可复核验证

| 命令/场景 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`，调用尚无的 `lock_installation` | 退出1，`unexpected keyword argument 'lock_installation'`，目标 RED |
| 同命令，试做 `FOR SHARE` 且仍仅八表 SELECT/RLS | 退出1，`InsufficientPrivilege: permission denied for table bundle_installation`；证明不能把纯 SELECT 等同锁权 |
| 同命令，最终隔离反证 | 退出0，1 passed、7 warnings。低权 `FOR SHARE` 被拒；Reader 持有 Registry advisory 时另一连接对同安装 `FOR UPDATE` 立即成功；另一连接取 `(228,1)` 在250ms lock_timeout 失败，Reader 提交后两个锁均可取得；角色 cleanup 后不存在 |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | 退出0，32 passed、2 strict xfailed、7 warnings |
| `py_compile` 目标测试、`git diff --check`、生产 Reader 相对 HEAD 的 `git diff` | 前两项退出0，生产 Reader 无差异 |

## 剩余风险和下一波

- 现有同事务 Reader 会取 Registry advisory，但没有安装行锁；安装 active/replace 可在两个检查点间竞争。SERIALIZABLE 也不能替代当前代码尚未持有的行锁、最终 CAS/Receipt 及正式 issuer 身份。b34/b37 strict xfail 保留。
- 下一波先设计受限、精确租户/安装 id/active/current/ETag 的数据库锁函数及执行权限。只在 test-only 恢复克隆先 RED 与最小权限试验；若需要新的 Alembic 迁移，当前卷切换另需新全备、全恢复克隆及零执行窗口。不要给正式 issuer 无界 UPDATE 作为捷径。当前正式角色/OIDC/Owner、八配置/六 Binding/自然首链仍 pending；Host/worker/Provider关闭。
