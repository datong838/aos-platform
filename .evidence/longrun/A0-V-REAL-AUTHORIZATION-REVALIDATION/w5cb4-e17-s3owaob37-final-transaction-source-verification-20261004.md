# E17-s3o-w-ao-b37｜最终事务签名来源复核切片验证

## 方案、代码与风险复审

- 已复习 231-2/3/4、BIND-1、b34–b36 和 `aip_capability_binding_service.py` / `aip_binding_readiness_service.py`。现有 readiness 的 Authority/Model 各自打开 Reader 连接；`evaluate` 在写事务前取结果，`update(...active)` 在 issuer 写事务内重算但仍用独立 Reader 连接。当前激活 UPDATE/Receipt 事务没有签名 Installation 来源与撤销锁，不能把先前读视图当作许可。
- 本波仅从 b36 的公开只读 Reader 抽出 `_read_unique_active_in_transaction`，由调用者提供连接和事务；原公开包装仍建立只读 REPEATABLE READ 事务、调用同一核心并返回 `EVIDENCE_ONLY_NO_START`。内部原语不 commit/close、不改变权限或最终激活逻辑；调用者仍须证明隔离级别、行锁、正式低权身份和最终事务 CAS。
- 新严格 xfail 固定“旧激活可在没有签名 active 安装重验时成功”的未闭合安全合同。**xfail 是待修缺口**，本波没有消除 b34 或 b37 xfail，也未完成正式 active/run 门。

## RED 与验证

| 步骤/命令 | 结果 |
| --- | --- |
| `test_unique_active_source_reader_reuses_caller_transaction_without_closing_it` 在实现前 | 退出 1，`AttributeError: ... _read_unique_active_in_transaction`，符合 RED |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py -q --disable-warnings --tb=short` | 退出 0，9 passed、7 warnings；当前 approved3/active NULL 在调用者事务中仍拒绝，连接可继续 SELECT |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | 退出 0，1 passed、7 warnings；仅 disposable PG/OCI 的 Growth1.13 active 安装证明同一调用方事务可复读签名来源。该 signer 仍 test-only，不是当前正式发布 |
| `services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/aip/test_aip_binding_readiness_service.py services/aos-api/tests/extension_runtime/test_release_revalidation.py` | 退出 0，23 passed、2 xfailed、7 warnings；原已知缺口和本波严格 xfail 均保留 |
| `py_compile` 四个变更文件、`git diff --check` | 退出 0 |

## 后续准入

- 下一波必须先证明 issuer 的正式低权角色可在最终事务访问当前 Installation/Registry/撤销证据，且锁/隔离/CAS 能使“检查后撤销/换代”无法放行。若权限合同需要迁移，只在独立备份+全恢复克隆+零执行窗口的迁移波处理。不能直接把这个内部证据原语接入 active/run。
- 当前真实库仍只读 `a0v_135`、Installation approved3/active NULL、Host/worker/Provider关。`org-org/dev-project` 唯一正向，`dev-org` 零副作用；无商城源读取、旧12 Run重放、手工 Run、230 L0 或 push。
