# GW-b-1 accepted-stage Handoff envelope：失败封闭语法切片

2026-10-02 05:50 CST。依据 231-5 §9 与 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md`，只改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 和 `services/aos-api/tests/extension_runtime/test_ecommerce_review_advance_host.py`。新 `sourceKind=accepted-stage-v1` 有独立字段集、hash、原 Stage exact refs、单 `Artifact`、TaskSpec 与中文业务文字检查；不借 OPEN ReviewIssue 或四个 `ArtifactRevision`。宿主的 revalidate/execute 明确拒绝，verify 不接受回执。原 Issue 分支保持原字段与行为。

RED：`.venv/bin/pytest -q tests/extension_runtime/test_ecommerce_review_advance_host.py::test_accepted_stage_source_has_a_distinct_strict_envelope --disable-warnings --tb=short` → exit 1，`invalid envelope`。最小代码后同命令 → 1 passed；宿主专项 `test_ecommerce_review_advance_host.py` → 20 passed；相邻 `test_ecommerce_review_handoff_content_runtime.py`、`test_sales_weapon_content_task.py` 合并 → 44 passed；原 Review Task/Brief PG → 3 passed。`python3 -m py_compile`、`git diff --check` → exit 0。

复审边界：语法通过不授予来源权限。producer 尚未生成该命令；原 `AnalystStageDecisionStore` 当前接受、审批 successor、Task/Brief v3、生成/评审来源复核仍缺；当前真实库只读、Host/worker/Provider 关闭。下波需 bundle producer 与 Host 原 Owner 同波 RED/最小实现；无自然首链验收。
