# GW-b-2c2c1b3a Growth 1.12 签名包完整 schema 批准安装

基线 `AOS-001110` / `aos-platform/m1 ccf013e9`；方案为 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` c1b3 节。测试只在 pytest 自动创建并销毁的 `aos_test_*_ti4_test@a0v_134` 数据库运行，输入为 BG00dj r3 本地开发签名 receipt。当前权威库 `aos_current_preview_20260927@a0v_118` 未写。

只读来源复核：`a0v_growth_112_successor_clone.check_signed_receipt` → `SIGNED_POLICY_OK`，四包签名树 `sha256:48a89116323d0327243690a6894a3647ba298e7874311dbe63d5a4716b6fdada`，Growth contentHash `sha256:ca604f9b18dba305dfaa54bc6e47006e512fd6c810888fdeb41a223057be6bd1`。归档 1.12 候选后端与今天 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth` 比较：同名 Python 4 文件已变化，当前多 1 文件；因此本波只证明历史签名包基础设施，不代表今天 accepted-stage 命令已打包。

新增 `test_growth_signed_installation_full_schema_pg.py`：从显式环境变量读取归档 receipt；原 FileTrustRootProvider/ManifestLoader/RegistryService 注册发布四包；原 `create_approved_first_installation` 经 Composition/Installation Store 产出 approved@3；回读 lock 中唯一 Growth 1.12 resolved member，`require_growth_registration_claims` 验九 API。runtime binding=0，dev-org 安装=0。新测试首次 RED 为 Registry `ManifestInvalidError: manifest metadata does not match the target bundle`，原因是测试传入包 ID 作 displayName；改用已签 manifest 原 displayName 后 GREEN，无生产代码修改。

验证：`AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH112_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json .venv/bin/pytest -q tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py tests/extension_runtime/test_accepted_stage_signed_source_pg.py tests/extension_runtime/test_ecommerce_growth_registration_qualification.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_lifecycle_service.py --disable-warnings --tb=short` → 51 passed、7 warnings、退出 0；`py_compile`、`git diff --check` 退出 0；OCI owner 容器无残留。

下一步 c1b3b：在同一签名 Growth full-schema fixture 经原 runtime-apply/verify；若旧 1.12 包的 schema/后端与当前代码不兼容，保留 fail-closed 证据并规划新不可变版本，不能改旧签名树。之后正式八配置、首登记、cutover 审批、自然 Occurrence/Analysis/Stage 仍需逐段正反链。当前正式信任根、三身份、Host Owner 未齐。
