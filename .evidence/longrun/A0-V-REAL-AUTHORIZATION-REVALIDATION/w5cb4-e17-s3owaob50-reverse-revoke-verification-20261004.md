# b50｜评估先提交、Registry 撤销等待

## 方案/代码复审

- 按 231-3/BIND-1 与 b48/b49 先写文件级计划；只在原完整 signed Growth1.13 disposable PG/OCI 测试入口新增 `AOS_B50_EVALUATE_FIRST=1` 分流。helper 缺失时专项 RED exit1 `NameError: _assert_evaluate_first_revoke_waits`。
- 新 test-only helper 在受限事务里用当前安装/Registry 行锁执行 **blocked/PENDING** evaluate，Binding version2→3 但未提交时第二连接 Receipt0；原 `RegistryService.revoke` 在线程启动，`pg_locks` 证其等待 `(228,1)`。评估提交后唯一 `first` Receipt1，随后原撤销生产者提交 `revoked`；旧来源 `after` 受限调用42501、Receipt0、Binding仍version3。线程和锁等待有界，原 test-only 函数/角色 finally 清理。
- 正反顺序现在各有隔离证据：b49 撤销先提交后旧快照失败，b50 评估先提交时撤销等待。它们没有证明安装换代、签名字节/信任根/evidence freshness/八依赖同事务可信正向，也没有生产迁移或正式角色。`FOR SHARE` 所需 test-only NOLOGIN definer 列级 UPDATE 权限仍待正式最小权限审查。当前真实库135只读，Host/worker/Provider关。

## 命令、退出码

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_B50_EVALUATE_FIRST=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | helper 缺失 RED exit1；实现后 exit0，1 passed/7 warnings。 |
| 相同完整命令分别设置 `AOS_B49_CONCURRENT_REVOKE=1`、`AOS_B48_COMMITTED_REVOKE=1` 和不设置模式 | 各 exit0，1 passed/7 warnings；原三路径未回退。 |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | exit0，32 passed/2 strict xfailed/7 warnings。 |
| `compileall -q` 两测试文件、`git diff --check` | exit0。 |

## 下一项

- b51 在独立完整克隆复习原 Installation 生产者，再造 active/ETag 换代与评估并发，不能用 admin 直改安装头冒充生命周期事件。另审正式 source 行锁权限，继续构造实际签名/全部依赖同最终事务的可信 evaluator 证明；缺正式 authority 只禁当前实例。
