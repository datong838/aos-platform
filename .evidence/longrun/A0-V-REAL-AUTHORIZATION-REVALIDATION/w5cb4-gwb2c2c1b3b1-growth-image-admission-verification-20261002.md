# GW-b-2c2c1b3b1 Growth 1.12 隔离镜像与原 admission

基线 `AOS-001111` / `aos-platform/m1 5d8151be`。方案 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` c1b3b 节。归档 r3 签名树只读；当前权威数据库未写，Host/worker/Provider 未启。

前检 `docker --context colima-aos-extension image inspect sha256:774bb27a…24e695` → No such image；仓外新输出与 receipt 路径均不存在。按原 build profile 在 `colima-aos-extension`、registry port 18438、`--retain-artifacts` 重建 1.12 候选到 `.aos-growth-112-build-20261002-c1b3b-v1`，receipt `.aos-growth-112-build-receipt-20261002-c1b3b-v1.json`；退出 0、`BUILD_GREEN`。与 BG00dj r3 比对：输出树 `sha256:91f6b050…166466` 相同，core/niushop/growth 三包 imageDigest 与 configDigest 均相同。新 build HEAD 为 `5d8151be`，这不改变归档 r3 开发签名身份，也不能充当当前正式签名。

测试 `test_growth_signed_installation_full_schema_pg.py` 扩充原 `admit_schema_requirements` 与 `admit_runtime_artifact`：从 disposable full-schema DB 的 Registry `_SNAPSHOT_QUERY`/`_record_from_row` 回读当前发布证据，与 Composition resolved exact member 及已签 artifact 原字节、隔离 OCI 缓存精确匹配。首次 RED 为直接用归档 loaded evidence，报 `bundle release evidence revision is stale`；改为原 RuntimeReleaseRevalidator 所读的持久化 Registry 记录后通过。三包各一条 schema requirement、image config digest 与签名索引一致。

专项及相邻：`AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH112_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json .venv/bin/pytest -q tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py tests/extension_runtime/test_accepted_stage_signed_source_pg.py tests/extension_runtime/test_ecommerce_growth_registration_qualification.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_lifecycle_service.py --disable-warnings --tb=short` → 51 passed、7 warnings、退出 0。`py_compile`、`git diff --check` 退出 0；`docker --context colima-aos-extension ps -a --filter label=aos.extension.owner` 无 Host 容器。

结论仅为隔离镜像可用与原只读 admission。原 `extension_schema_installation` 还需维护角色以 exact requirement 记录真实已有共享 schema；runtime apply/verify、配置、首登记、cutover、自然经营链仍未做。c1b3b2 应在同一 disposable DB 以原 `apply_once` 校验物理关系，再经原 PreparationWorker 正反测试；1.12 历史 backend 的今日代码差异继续保留为发布阻断。
