# W5ca6｜A0-V 权威记忆下一步去过期行动项方案

## 上位与范围

复习 231 的 A0-V→A1 串行门、230 L0 挂起、W5ca5 外部 Fleet/历史行权威缺口及 AOS-000720。当前权威 `next_steps` 同时保留 W5c8a–f 的旧“先方案”行动，而六波 verification 已分别在 m1 `5dd544cd/c65bc58a/04591d78/0e86ad3c/649a039c/7d923a5c` 提交。过期行动项可能诱导重复执行；但其所附真实迁移、Host/源组权威缺口仍需保留在 `incomplete`，不可借本波宣称关闭。

## 文件级清单与验收

- 只读：六份 W5c8a–f verification、W5ca4/5 verification、`docs/palantier/AOS项目开发上下文/memory/authority.json` 的 `next_steps/incomplete`、231 主线。
- 变更：只经 `scripts/memory/memoryctl.py authority-update` CAS 将 `next_steps` 收敛为一条当前外部权威/正式退休决策门；自动投影更新 `docs/palantier/AOS项目开发上下文/memory/{authority.json,events/2026-09-26.jsonl,projections/aos-project.json}`、`01-当前项目状态.md`、`06-当前执行检查点.md`，并更新 D-waves 接力注记。不得直接手改生成投影或删 `incomplete`。
- 证据：本目录新 audit/verification；docs 上下文编号 152；Prime 独立记忆经既有 `memory-sync` 读回。
- 验收：CAS 必须从 AOS-000720 前进一次，`next_steps` 不再含 W5c8a–f“先方案”；`incomplete` 仍含原十二 Run、Fleet/Host、历史行、真实迁移等硬门；`memory-validate` GREEN，`memory-status` 至少维持 GREEN_WITH_WARNINGS，git 精确提交。若 revision/hash 漂移，冻结不覆盖。

## 九步与停止线

1. 上位方案复习；2. 本方案先提交；3. 六份 verification/权威 JSON 静态复核；4. 最小 CAS；5. 专项 JSON/投影与累计记忆校验；6. 18181 仅文档只读/8080 离线如实记录；7. 方案/结果一致性复审；8. audit/verification、D-waves、AOS/Prime 记忆、精确提交；9. 自动进入下一波。任何未知 CAS/同步结果先只读对账，不重复更新。

本波没有业务 endpoint、商城源、原组 closure、`run_definition`、Store/Receipt/Run 写入，不 push；dev-org 只作零 canary。
