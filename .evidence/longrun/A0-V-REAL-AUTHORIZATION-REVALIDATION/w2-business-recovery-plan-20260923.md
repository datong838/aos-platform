# W2 业务恢复波 — plan (2026-09-23)

## 上位方案复习
- RC 根因波（4b2f2a0f）钉死：字母链 64 次失败 = 「换安装重试」与「冻结上下文一致性校验」的结构性冲突 + attempt 不落子码；当前暂停态另有 budget policy rev11 过期（2026-09-22 12:05 UTC）独立障碍。
- 231-9 BG-00 要求产品入口恢复；本波目标是**复活 12-OT 业务数据管道**（BG-02 的前提）。

## 本波文件级清单
1. **budget 续租**：`scripts/a0v_formal_text_model_renewal.py --apply`（EVIDENCE_DIR 指向 `.aos-recovery-20260910/state/a0v-exact-text-live-eval`，legacy-v1 profile）→ 产出 rev12，恢复 `budget policy is effective`。
2. **attempt_target 重放验证**：续租后重跑 `a0v_rc_conflict_replay.py`，确认 attempt_target / projection_completion 转 OK（definition disabled 的冲突仍会在，属预期）。
3. **解卡 12 僵尸 run**（合法路径）：
   a. 启动 aos-api 服务（18181）与前端（8434 已有 vite dev）。
   b. 用恢复权威（recovery executor = `a0v-ecommerce-growth-1.4-runtime-owner`）经 `PipelineSnapshotScheduleWorker.run_definition` 路径触发 `resume_saved`，让 attempt 走完校验链；若 `_route` 因中间态卡死（INGRESS_STOPPED_FAILED_RUN_REQUIRED / GROUP_RUN_STATE_CHANGED），则按 `ec_ingress_claim.claim_failed_run` 的要求走 run 状态收敛路径。
   c. 每 run 落 failed+stopped+finished_at（幂等 Receipt）。
4. **definition 启用**：经产品 API（`/v1/.../definitions` 启用端点或 workshop UI）把 definition 268→269 enabled，触发自然 dispatch。
5. **观察自然 dispatch**：worker tick 15s → 下一次 staggered cron 到点 → 12 OT 新 run 全部 succeeded。
6. **浏览器验收**：workshop 前端（8434）确认调度页 12 schedule 显示 enabled + 最近 run succeeded；截图存证 `.evidence/.../w2-browser-verification/`。

## 退出条件
- budget rev12 生效；重放无 definition/budget 冲突（除预期 disabled 冲突）。
- 12 个旧 run 终态化（failed+stopped 或恢复完成）。
- 新 group 一次自然 dispatch 全绿（12/12 succeeded）。
- 浏览器截图 + verification 文档 + git commit。

## 风险与边界
- 续租和 enable 都是权威 API 操作（带 If-Match/幂等键），失败即停，不手改库。
- 若 resume_saved 仍撞子码：记录子码（现在会落 attempt 表？——不会，仍无列），改用 evidence 记录，停波不猜。
