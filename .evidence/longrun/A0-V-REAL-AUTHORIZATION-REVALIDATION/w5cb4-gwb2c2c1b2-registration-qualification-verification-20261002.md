# GW-b-2c2c1b2 首登记签名资格负合同

基线 `AOS-001109` / `aos-platform/m1 cf229032`。复习 231-3 configure/enable、231-5 §9、原 `FirstDispatchRegistrationService.register`、`qualify_registration_release` 与 `EcommerceGrowthCutoverStore.prepare_activation`；文件级计划在 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` c1b2 节。

发现：c1a/b1 使用的 OCI 签名测试包由 `test_persistent_supervisor.build_session_image` 构造，只有 `/example/read` 声明；正式首登记资格锁定 `solution.ecommerce.growth`、SolutionPack 与九条 exact Growth API，再在同一事务回读当前签名/Registry/lock。首登记生成 fenced legacy dispatch 和 Receipt；启用/配置与 AIP cutover 独立审批均有各自原 Owner，不能用测试签名包或手插 dispatch 跳过。

RED：给 verify probe 增加 lock、policy 必需参数后，专项因 helper 未传参数报 `TypeError`，退出 1。最小修复只在测试 helper 的可选 probe 传入已有原 lock 与 ReleasePolicy；默认 helper 路径及生产代码不变。随后原 `qualify_registration_release` 对同一已验证签名安装给出 `REGISTRATION_GROWTH_PACKAGE_REQUIRED`；该安装下首登记 Receipt 与 extension dispatch 都是零行。

验证：`AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 .venv/bin/pytest -q tests/extension_runtime/test_accepted_stage_signed_source_pg.py tests/extension_runtime/test_ecommerce_growth_registration_qualification.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_lifecycle_service.py --disable-warnings --tb=short` → 50 passed、7 warnings、退出 0（最后的 dispatch 零行断言追加前）；追加后专项 1 passed、7 warnings、退出 0。`py_compile` 与 `git diff --check` 退出 0；OCI owner 容器无残留。

结论仅为合法禁入。下一波 c1b3 应用已有 Growth 1.12 候选的构建、资格与本地签名链，产出隔离可重复的 full-schema signed Growth 安装来源；随后使用原配置/首登记/AIP cutover producer 逐段接线。本地签名不是当前正式信任根，当前库、Host/worker/Provider 仍不写不启。
