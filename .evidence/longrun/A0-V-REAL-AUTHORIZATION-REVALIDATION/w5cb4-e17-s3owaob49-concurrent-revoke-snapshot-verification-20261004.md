# b49｜撤销竞争时旧 SERIALIZABLE 快照失败关闭

## 复审事实

- 复习 231-3/BIND-1 与 `RegistryStore.transition_version`：原生产者先锁 advisory `(228,1)`，再锁版本/证据行并提交状态与生命周期事件。b48 test-only 命令先锁安装，再等待 advisory，原来等待后以普通 SELECT 查询 current published。
- 完整 signed Growth1.13 disposable PG/OCI 中用三连接确定顺序：A 锁 release 行；正式 `RegistryService.revoke` 在 B 获 advisory 后等待 A；低权受限命令 C 锁安装并等待 advisory；A 放行后 B 撤销提交，C 继续。`pg_locks` 验证 B 持锁及 C 排队，均有界超时。原函数 C 仍以旧 SERIALIZABLE 快照写新 Receipt，RED exit1 `AssertionError: applied`；共同 advisory 本身没有解决事务快照新鲜度。
- 最小修补仅在 test-only 受限函数的 exact Registry release 查询使用 `FOR SHARE OF v`；版本已被撤销更新时，旧 SERIALIZABLE 事务必须失败关闭，Binding/撤销竞争键 Receipt 不增加。PG 行锁要求 UPDATE 权限，因此只给该 test-only NOLOGIN definer `asset_bundle_version.status` 列级 UPDATE，低权 EXECUTE caller 没有来源 UPDATE。该角色尚不能作为正式最小权限设计，必须独立审查/迁移。
- b49 验证的是**撤销先提交、评估后醒来**一个方向；评估先提交后撤销、安装换代、信任根/证据过期、实际 Loader/ReleasePolicy 和八类依赖的同事务可信 positive evaluate 仍待。函数依然只能写 blocked/PENDING；无生产代码/迁移或当前真实库写。Host/worker/Provider 仍关闭。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_B49_CONCURRENT_REVOKE=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | 修补前 RED exit1 `AssertionError: applied`；带锁查询后 exit0，1 passed/7 warnings。中间仅加行锁而未授 test-only definer 列级权限时，原正向因 `InsufficientPrivilege` 失败，权限补齐后复跑通过。 |
| 相同命令去掉 b49 模式 | exit0，1 passed/7 warnings，正常完整安装路径未回退。 |
| 将 b49 模式换为 `AOS_B48_COMMITTED_REVOKE=1` | exit0，1 passed/7 warnings，已提交撤销负门仍在。 |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | exit0，32 passed/2 strict xfailed/7 warnings。 |
| `compileall -q` 两测试文件、`git diff --check` | exit0。 |

## 下一门

1. b50 应补相反提交顺序及安装 ETag 换代，检验两种竞争后的唯一 Receipt/无半写；同时复审正式角色是否能用比 test-only `UPDATE(status)` 更窄的受限锁入口。
2. 正向 available 仍必须有可由 DB 验证的受信 evaluator 身份/证明，实际签名字节/信任根、evidence freshness 和全部当前依赖同最终事务。b34/b37/b44 xfail 未解除；正式 OIDC/Reader/Issuer/Owner、active Growth1.13、八配置/六 Binding 和自然首链待证。当前库135只读，唯一136迁移另波按新备份、全恢复、零执行窗口。
