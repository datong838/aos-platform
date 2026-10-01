# GW-b-2a 原 accepted Stage Owner 同事务读取

2026-10-02 06:08 CST。`ReviewAdvanceHostService._revalidate_accepted_stage_source` 从原 `read_approved_stage_handoff_source` 读取当前 accepted StageDecision、原 draft 与内容相同的获批 successor；明确比对 Artifact、EvalReport、ResponsibilityPlan、截止时间和租户。宿主 `revalidate` 在读完后仍报 `Task/Brief is not wired`；`execute` 继续失败封闭，`verify_receipt` 不认可新分支。

RED 1：`test_analyst_stage_handoff_source_pg.py::test_review_host_reads_original_accepted_stage_owner_in_same_transaction` → exit 1，缺 `_revalidate_accepted_stage_source`。补最小 Owner 读取后 → 1 passed。RED 2：布尔 stage revision 与 attempt 注入的两项测试 → 2 failed（Pydantic 隐式接受布尔）；增加原始 dict 严格字段和 `type(...) is int` 后 → 7 passed。最终五文件相邻回归 `.venv/bin/pytest -q tests/extension_runtime/test_ecommerce_review_advance_host.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py tests/extension_runtime/test_ecommerce_review_handoff_content_runtime.py tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py tests/test_sales_weapon_content_task.py --disable-warnings --tb=short` → **67 passed**, exit 0。

隔离 PG fixture 经原 Store 发布，不等于当前真实人工决策、自然事件或首链；测试命令中的旧 Occurrence/Case/Run/Analysis refs 尚未同原 Stage TaskRun 联合核验。bundle producer、Task/Brief v3、内容生成与评审同源校验仍待。当前真实库只读，Host/worker/Provider 未启用，旧 Issue 路径保持。
