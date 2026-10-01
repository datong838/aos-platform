# GW-b-2c2c1b1 签名安装至原 Case 与 dispatch 禁入

基线：`AOS-001106` / `aos-platform/m1 491d1b7b`；方案 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` 的 c1b1 节，231-5 §9。所有写入都在 pytest 创建并销毁的 `aos_test_*_ti4_test` 数据库；OCI 测试容器独立，当前权威库 `aos_current_preview_20260927` 保持只读。

改动：`services/aos-api/tests/extension_runtime/test_accepted_stage_signed_source_pg.py` 在原签名安装 verify probe 中调用原 `BusinessInvestigationCaseStore` 创建、激活并回读 Case。用同一安装 ID/generation/epoch 构造 ScheduleBinding，由原 `AutomationOccurrenceStore.put_binding` 校验；因尚无正式 `extension_operation_dispatch_binding`，得到 `AutomationOccurrenceNotReady("schedule binding does not match current dispatch")`，且该 policy 下 `automation_schedule_binding`、`automation_occurrence` 均为 0。这不是手插 dispatch 或人工 Run。

验证：

- `AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 .venv/bin/pytest -q tests/extension_runtime/test_accepted_stage_signed_source_pg.py --disable-warnings --tb=short` → `1 passed, 7 warnings`，退出 0（最后的两表零副作用断言已包含）。
- 相邻 `test_accepted_stage_signed_source_pg.py test_analyst_stage_handoff_source_pg.py test_lifecycle_service.py` → `33 passed, 7 warnings`，退出 0（两表断言追加前；专项追加后再绿）。
- `python3 -m py_compile services/aos-api/tests/extension_runtime/test_accepted_stage_signed_source_pg.py`、`git diff --check` → 退出 0；`docker --context colima-aos-extension ps -a --filter label=aos.extension.owner` → 空。

结论：原签名安装与原 Case producer 已在同一完整 schema 联通；当前合法 dispatch 缺失被原 Occurrence Store 精确禁入。尚无正式配置/批准/启用、dispatch、自然 Occurrence、Analysis Receipt、Stage 或业务首链。下一步 c1b2 复用原 `RuntimeConfigurationService` 与 `EcommerceGrowthCutoverStore`，查明 full-schema 正式配置来源、原 AIP cutover approval 与 dispatch producer 的先后及身份；不能沿用历史局部 schema 测试直接写 approval/dispatch 的夹具。
