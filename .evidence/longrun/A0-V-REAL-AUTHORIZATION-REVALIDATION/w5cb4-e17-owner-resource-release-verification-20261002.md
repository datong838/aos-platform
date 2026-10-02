# E17 Owner 前置：已观察释放资源不可作为运行证据

## RED 与 GREEN

- Task Receipt：`W5CB4-E17-OWNER-RESOURCE-RELEASE-20261002`；方案见同名前缀 `plan`。原 Growth 1.13 本地签名 Registry→安装→runtime-apply/verify→OCI 在独立 `aos_test_*_ti4_test` PG 中形成 active/current、ready 但 disabled/fenced 的 binding。仅将该测试库同代资源的 `observed_release` 标为 true，其余 cleanup/lease 不变。
- RED：`AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_TEST_RETAIN_DATABASE=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` → `1 failed, 7 warnings`，退出 1：`Failed: DID NOT RAISE CurrentReleaseEvidenceBlocked`。测试最终恢复测试行的 release 标记。
- 最小实现只在 `current_installation_release_evidence.py` 同一只读事务的资源查询里加入 `observed_release`，该值不为严格 false 时复用 `RUNTIME_RESOURCE_NOT_LIVE`。相同命令 GREEN：`1 passed, 7 warnings`，退出 0；正常未释放证据仍可读，释放负例被拒。测试使用本地测试签名，绝非当前正式 trust。
- 相邻无 PG 组：`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 PYTHONPATH=services/aos-api .../pytest -q --tb=short --disable-warnings test_current_installation_release_evidence.py test_a0v_current_runtime_host_preflight.py test_a0v_ecommerce_runtime_host.py` → `42 passed, 5 skipped, 7 warnings`，退出 0。5 skipped 是缺显式当前签名 receipt 的只读专项，不计作通过。`py_compile` 与 `git diff --check` 退出 0。
- 遵守不删除库/卷/备份，本轮两个 pytest 自动创建的隔离测试库以 `AOS_TEST_RETAIN_DATABASE=1` 保留：`aos_test_67d0d5e74fe4_ti4_test`（RED）与 `aos_test_e16ab6e3bcf4_ti4_test`（GREEN），位于 `aos-a0v-test-pg`，未改当前权威卷。后续另立清理清单，不在本波删除。OCI owner 残留查询为空。

## 复审与限制

符合 231-3 的资源存活前提及原 rehydrate 的 `observed_release` 拒绝规则。该读者始终只返回 `EVIDENCE_ONLY_NO_START`；正式 selector 仍只返回 `PREFLIGHT_ONLY_NO_RUNTIME_START`，Host 固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。当前实例八配置、正式 OIDC/三身份、Growth1.13 正式发布和 assignment/binding 仍缺；这项修复不构成启动或首链证明。无 UI 改动；本日完整重启的八页浏览器禁入验收仍有效。下一波按 E17 正式身份/配置 Owner 或原 Review producer 推进。
