# GW-b-2c2a 当前 Occurrence/Case 共用入口验证

2026-10-02 约 06:55 CST。基线 `AOS-001102` / `m1 ff963704`，方案见 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` 的 GW-b-2c2 节。复习 231-5 §9、231-9 原增长链、D-waves GW-b-2c2 后改动。

RED：`test_ecommerce_review_advance_host.py -k checks_current_occurrence_and_case_before_stage_source` 退出 1，2 failed；两例均在 Stage 读者处抛 AssertionError，证明旧 accepted-stage 分支跳过当前 Occurrence/Case。最小改动将旧路径的当前 Occurrence payload hash、Case 当前 head/ref 核验抽为共用方法，在两种来源分叉前执行。六文件相邻回归 85 passed、7 warnings、退出 0；包含旧 Issue 正向与隔离 PG Stage 来源负向。`py_compile` 和精确 diff check 须提交前复核。

现有 Stage PG fixture 无当前 Occurrence，宿主现在正确报 `AutomationOccurrence authority is missing`。单元测试的 _components 是受控读者替身，只证明调用顺序及拒绝，不构成当前真实实例、真实联合 PG 生产者或人工批准证明。Stage Eval/permission、原 BI→Stage PG 联合正向、Task/Brief v3、内容生成/评审仍未接通；`execute` 保持禁入。真实库只读，Host/worker/Provider 关闭。
