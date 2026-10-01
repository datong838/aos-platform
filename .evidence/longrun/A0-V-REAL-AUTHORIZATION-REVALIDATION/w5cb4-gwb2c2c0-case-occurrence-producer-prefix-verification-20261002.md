# GW-b-2c2c0 原 Case/Occurrence producer 前缀

基线：2026-10-02，`AOS-001104` / `m1 5092d55d`。方案：`w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` 的 GW-b-2c2c 施工表与 c2c0 补充。唯一测试目标为隔离 `aos_test_*_ti4_test` PG；当前真实库保持只读。

RED：新测试最初用直插安装行，提交时被 `fk_bundle_installation_current_revision` 拒绝，证明这种夹具不能充当合法安装。改用原 Composition/Installation Store 后，首次被缺 `meta_workspace` 的合法 FK 拒绝；补测试 workspace 后，Occurrence 的非 UUID 安装身份及非秒精度时间先后被原合同拒绝。以上均未绕过 FK/RLS/时间合同。

GREEN：原 `BusinessInvestigationCaseStore` 产生同租户当前 ACTIVE Case；原 `AutomationOccurrenceStore.put_binding/record_scheduled` 产生当前 Occurrence。宿主同事务读取两者后抵达预期的 `AnalysisRuntimeReceipt authority is not unique` 缺来源拒绝点。运行 `services/aos-api/.venv/bin/pytest -q tests/extension_runtime/test_analyst_stage_handoff_source_pg.py --disable-warnings --tb=short`：20 passed、7 warnings、退出 0。

相邻回归：`services/aos-api/.venv/bin/pytest -q tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_automation_occurrences_pg.py tests/test_ecommerce_business_investigation_lifecycle.py --disable-warnings --tb=short`：26 passed、23 skipped、7 warnings、退出 0；`python -m py_compile` 和精确 `git diff --check` 均退出 0。23 skipped 为该测试环境现有跳过项，不能算通过或当前实例证明。

范围：Composition/Installation draft 是测试来源；runtime binding/dispatch 由隔离控制面夹具建立，非当前正式签名安装。StageDecision/批准人亦是测试值。没有真实 Analysis/Stage/AgentRun/Eval 全链、Task/Brief v3、当前 Host 执行或自然首链。本前缀仅把下一最小缺口定位为原 Analysis Receipt producer；不可作为业务准入。
