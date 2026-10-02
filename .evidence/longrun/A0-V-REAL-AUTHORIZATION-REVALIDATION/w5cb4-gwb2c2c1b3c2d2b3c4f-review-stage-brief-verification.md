# d2b3c4f 验证｜内容评审读取原阶段与 v3 Brief

2026-10-02 15:20 CST。起点 `AOS-001137`、`aos-platform/m1 dad540c6`；方案 `w5cb4-gwb2c2c1b3c2d2b3c4f-review-stage-brief-plan.md`，代码提交 `91d5fe05`。复习 231-5 §9、231-9 与 BG00gw 清单。仅修改 Review Host 读者与两份测试，当前真实库只读。

| 检查 | 本次结果 |
| --- | --- |
| RED | 新 PG 测试调用缺失的 `_accepted_stage_task_brief_authority`，`AttributeError`、1 failed，退出1；测试会话在 `aos_test_*_ti4_test` 自动建销。 |
| 最小实现 | 新来源先核精确 dispatch、数据库当前时间与可读内容 Artifact；从 Task.goal 提取候选 lineage/Handoff 并重算 Handoff hash，再复用原 Stage Owner、持久 Review Receipt 和 v3 Task/Brief 读者。任一缺失拒绝；末端仍 `Host is not wired`。旧 Issue 分支、execute、verify 仍原门。 |
| 专项/相邻 | 原 Task/Brief PG、Review authority/feedback、内容生成 Handoff lineage 三文件 `43 passed, 7 warnings`，退出0；`py_compile`、精确 `git diff --check` 退出0。隔离 PG 原 StageDecision/GrowthPlan Owner 可读，缺原持久 Review Receipt 报 `Review authority is not unique`。测试中仅为验证后续 v3 Brief 读者使用局部 seam；它**不能**证明正式 Receipt 或自然首链。 |
| 当前栈 | 提交后既有 API LaunchAgent `kickstart -k` 退出0，新 PID53331；`/v1/health`、`/v1/ready`、Web `/aip/skill-publish` 均200。权威库只读回读 `aos_current_preview_20260927@a0v_135`、正租户 binding/assignment/runtime command Receipt 均0；18181无监听。此次是 API 重载，并非 PG/API/Web 全量重启。 |
| 浏览器 | Codex 内置浏览器重载技能发布页：37项仅评测、发布0；正式发布决定/事件、Logic 版本、模型路由/运行策略三 blocker；按钮 disabled；电商工作台无可见入口。截图 `w5cb4-gwb2c2c1b3c2d2b3c4f-browser.jpg`，SHA256 `8de4dbc8d778ed9333417f25827448798b7adf948f1791314a40a12a59062746`。 |

复审：代码保持 231-5 §9 的单原 Artifact、原 StageDecision/批准 successor、同组 Handoff/Receipt/TaskBrief exact refs；没有将 fixture 决定当成人工批准，也没有打开 Host。现有完整原 Analysis/G2 生产者与**真正持久化** Review Receipt 的联合正向仍缺；内容 Eval/Issue、独立人工 ACCEPT/RETURN、反馈与终态待接。当前正式 OIDC、Growth1.13 发布/Owner、八配置、Host identity/assignment/binding 仍阻断当前实例。Prime LaunchAgent 在列表中，原 agent.jsonl 最近写入为9月29日；本波无模型调用证明。记忆状态待同步回读。
