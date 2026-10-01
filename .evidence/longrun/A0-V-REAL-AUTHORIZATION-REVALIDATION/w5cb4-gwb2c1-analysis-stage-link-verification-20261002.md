# GW-b-2c1 原 Analysis Receipt 至 Stage TaskRun 的受限关联

2026-10-02 06:30 CST。`ReviewAdvanceHostService._revalidate_analysis_runtime` 原本回读 AnalysisRuntimeReceipt、BI Run/State、compilation receipt、Task/Plan/TaskRun 并以 Binder 核同源，终点只接受 TaskRun SUCCEEDED。本波仅对经 `accepted-stage-v1` 和原 Owner 决策 TaskRun ID 双重匹配的分支放行 RUNNING/PAUSED/SUCCEEDED；原 Issue 路径仍只认 SUCCEEDED。`revalidate` 先读原 accepted Decision，再回读原 Analysis Receipt，之后仍报 `Task/Brief is not wired`；`execute` 不变。

RED：`test_ecommerce_review_analysis_runtime_authority.py::test_accepted_stage_links_running_original_task_run_without_relaxing_issue_review` → exit 1，缺受限参数。最小实现后该文件与原 Stage PG 合计 31 passed；六文件相邻回归 83 passed，退出码 0。PG fixture 仅有 StageDecision 而无原 Analysis Receipt 时，宿主明确报 `AnalysisRuntimeReceipt authority is not unique`，不能绕过原链。静态 `py_compile` 和精确 `git diff --check` 均退出 0。

局限：`test_ecommerce_review_analysis_runtime_authority.py` 使用受控读者快照，不是当前实例原 BI→Stage 自然生产；目前没有原 Occurrence 当前权威与 Stage Eval/permission 的 Handoff 时复验，也没有 Task/Brief v3、内容生成/评审。真库只读，Host/worker/Provider 关闭，不手工 Run、不回放旧 12 Run。
