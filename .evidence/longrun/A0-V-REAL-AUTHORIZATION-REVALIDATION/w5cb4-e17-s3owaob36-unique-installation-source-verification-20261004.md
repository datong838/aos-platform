# E17-s3o-w-ao-b36｜唯一当前安装签名来源 Reader 验证

## 方案与改动复审

- 对照同目录 `w5cb4-e17-s3owaob36-unique-installation-source-plan-20261004.md`：仅增只读 Reader，并复用既有 `_read_exact_in_transaction` 的 Registry、签名、锁与本地字节重验；没有新增表、迁移、当前实例写入或运行授权。
- 选择键是租户、SolutionPack publisher/id/version/contentHash、`active_revision=current_revision`、当前 revision 的 `active` 状态；同一只读 REPEATABLE READ 事务内取至多两个候选。零个及多个均失败关闭，唯一候选仍走原精确安装重验，返回 `EVIDENCE_ONLY_NO_START`。
- 当前权威安装仍是 approved@3、active_revision NULL，所以当前真实库验证应当返回 `ACTIVE_INSTALLATION_MISSING`。此项仅收口来源选择机制，不解除 b34 strict xfail，也不把隔离测试库的 Growth 1.13 视作当前正式发布。

## RED、专项和相邻回归

| 命令/步骤 | 结果 |
| --- | --- |
| 新 Reader 测试先行，调用不存在的函数 | `1 failed` / `AttributeError`，符合 RED |
| `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py -q --disable-warnings --tb=short` | 退出 0，8 passed，7 warnings；含当前 approved、错 hash、跨租户和多候选禁入 |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | 退出 0，1 passed，7 warnings；仅独立 test-only 库的签名 active 正向和错 hash 反例 |
| `services/aos-api/.venv/bin/python -m pytest -q --disable-warnings --tb=short services/aos-api/tests/extension_runtime/test_release_revalidation.py services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py` | 初次与另一独立库测试并行时退出 1：迁移 `ALTER ROLE aos_runtime` 遭 `tuple concurrently updated`，13 个 setup error；串行重跑退出 0，13 passed，7 warnings。环境并发冲突如实保留，不作为产品缺陷或业务通过证据 |
| `services/aos-api/.venv/bin/python -m py_compile` 三个变更文件；`git diff --check` | 均退出 0 |

## 当前边界与下波

- Reader 未接 AIP readiness、activation 或 runtime 最终事务；独立低权限身份与当前正式 OIDC/Owner/Host assignment 仍缺，不能据此启 Host、worker、Provider。
- 当前安装/签名来源和业务首链仍 pending；真实库只读，`org-org/dev-project` 唯一正向租户，`dev-org` 零副作用；不读取商城源、不重放旧 12 Run、不手工 Run、不碰 230 L0。
- b37 先复习 231/BIND-1、现有 AIP capability readiness 和 runtime 最终事务边界，写文件级方案与 RED；只在同事务可重验且低权身份有证据时接线。独立配置/正式身份项继续并行排查，不凭此 Reader 宣称首链完成。
