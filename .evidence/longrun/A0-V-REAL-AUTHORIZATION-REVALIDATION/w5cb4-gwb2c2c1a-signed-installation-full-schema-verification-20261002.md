# GW-b-2c2c1a 签名安装 producer 与完整测试 schema

基线：`AOS-001105` / `aos-platform/m1 053c7473`。上位 231-5 §5/§9、231-9 §2/§4；文件级计划在 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md`。环境：pytest 自动创建并销毁 `aos_test_*_ti4_test` PG，代码头 `a0v_134`；一次性 OCI 容器使用 `colima-aos-extension`，与当前权威 PG 容器隔离，未连接 `aos_current_preview_20260927`。

RED/修正顺序：新测试先因签名 helper 不接受 `verified_probe` 退出 1；增加默认关闭的验证后回读点。完整 schema 又依次暴露 `aos_runtime` 对 public 无 CREATE 权限、`apply_once` callback 必须返回 `None`、worker 必须采纳 `aos_runtime`、runtime-verify 受理需要明确 `preparation_admission`。测试 schema migration 由测试库 owner 执行，worker 用其正式 runtime 角色连接；测试辅助入口沿用既有 test-only 准入 seam，不改生产服务/权限。

验证：`AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 services/aos-api/.venv/bin/pytest -q tests/extension_runtime/test_accepted_stage_signed_source_pg.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_lifecycle_service.py --disable-warnings --tb=short` → 33 passed、7 warnings、退出 0。回读签名 producer 的 active 安装、同 generation 的 runtime binding 为 `ready` 且 `enabled=false/operation_fence=true`。`docker --context colima-aos-extension ps -a --filter label=aos.extension.owner` 空；`py_compile`、精确 diff check 退出 0。

边界：这是隔离测试根、测试身份、测试 Host 准入；没有当前正式组织签名/独立 checker/配置/Host assignment，没有与原 Case/Occurrence/Analysis/Stage/AgentRun/Eval 同源联合。`a0v_118` 当前库未迁移或写入，真实首链未发生。旧 `test_installation_baseline_pg.py` 依赖未监听的 18432，未把本次 33 passed 冒充其历史用例已回归；后续恢复独立端口后需跑其 signed worker verify 相邻项。
