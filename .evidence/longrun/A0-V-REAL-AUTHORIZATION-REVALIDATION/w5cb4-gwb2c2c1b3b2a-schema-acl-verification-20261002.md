# GW-b-2c2c1b3b2a 原 schema 维护权限修复

2026-10-02 08:49 CST，基线 `AOS-001112` / `aos-platform/m1 a45c4ed8`。先复习 231-3 第3/6节、231-5 第9节、原 `schema_registry.apply_once`、`a0v_ecommerce_schema_receipts.verify_physical` 和完整 schema Growth 签名安装测试；文件级方案见 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` c1b3b2 节。

RED：完整 `a0v_134` disposable PG 中 `SET ROLE aos_runtime` 后 `has_table_privilege(current_user,'extension_schema_installation','INSERT')=true`，原 `apply_once` 没拒绝，专项 1 failed。诊断读取到 ACL `{aos_app=arwdDxt/aos_app,aos_runtime=arwd/aos_app}`；早期 TI-2 全表 default GRANT 赋予新表写权，`ar1_001` 对本表仅 GRANT SELECT，未 REVOKE。对当前权威库只读查询也回读 `a0v_118`、同一 ACL 与 `has_table_privilege('aos_runtime',...,'INSERT')=t`；没有对当前库写入。

最小修复：`a0v_135_extension_schema_acl.py` 只对 `public.extension_schema_installation` 撤销 PUBLIC/aos_runtime 全权限，再明确授予运行角色 SELECT；原 `schema_registry.apply_once` 在现行 ACL 检查前同时拒绝 `current_user=aos_runtime`，使尚未迁移的实例应用层也失败封闭。测试从已签 1.12 artifact 读取三个 exact schema requirement，先证明未安装拒绝，再用原 `verify_physical` 校 Alembic revision/13 物理关系、经原 `apply_once` 记录；在完整 `a0v_135` disposable PG 回读 `aos_runtime` 仅 SELECT 且原维护 API 拒绝其执行。

专项及相邻命令：`AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH112_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json .venv/bin/pytest -q tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py tests/extension_runtime/test_schema_conditions.py tests/extension_runtime/test_ecommerce_schema_receipts.py tests/extension_runtime/test_accepted_stage_signed_source_pg.py tests/extension_runtime/test_ecommerce_growth_registration_qualification.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_lifecycle_service.py --disable-warnings --tb=short` → 65 passed、7 warnings、退出 0。`py_compile`、`git diff --check` 退出 0；隔离 OCI owner 容器零残留。历史 `test_schema_registry_pg.py` 另需端口 18432 的独立 PostgreSQL，现场该端口无监听，四例因连接拒绝 ERROR；完整迁移图专项覆盖本次 ACL 边界，不将基础设施错误说成测试通过。

本切片仅修 schema receipt 维护权限并登记 signed 1.12 的物理 schema 事实；尚未执行原 PreparationWorker 的 runtime-apply/verify，也未完成配置、首登记或自然首链。当前真实库保持 `a0v_118`、运行服务仍为 9 月 30 日进程；代码迁移头变为 `a0v_135`，当日最新栈全重启需独立安全迁移与零执行门。Host/worker/Provider 不启。
