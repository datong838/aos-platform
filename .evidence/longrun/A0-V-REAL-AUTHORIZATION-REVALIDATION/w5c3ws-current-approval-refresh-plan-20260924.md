# W5c3wS 当前精确审批与冻结窗口刷新方案（2026-09-24）

## 起点

W5c3wR `3acee1b9` 已修复并经专用 PG 67 passed/1 skipped 证明 post-commit 冻结窗口可以正式刷新；活体 operation 仍 committed、九路 extension、claims paused，无 Validate Receipt。旧 approval event 07:07:15 UTC 已过期；旧 proposal 有效不能替代事件。此波不 validate/resume。

## 串行步骤

1. 只读核旧 Prepare/Commit Receipt、W5c3v 9/9 路由、Runtime/Host/三 held 资源、claim gate paused、零 running/claimed/unknown、12 schedule off、canary0/业务计数不变，刷新记录零。核新 proposal key 未使用。
2. 私有 0600 intent 固定与原批准完全相同的 cutover payload/policy、唯一新 approval key；调用现有 AIP Owner `_approve`，完成 maker + 两 checker 的正式审批。新 proposal/event/hash/期限只读回读，尤其要求 event 有足够剩余窗口。结果未知只读核 key，不重发。
3. 独立私有 intent 固定 RefreshRequest：原 operation、原 Prepare Receipt、上一步新 ActionApprovalEvent 精确 ref、新刷新 key。正式 `refresh_activation_approval` 一次；回读唯一 Refresh Receipt/newRef、九路/claim gate/Runtime/调度/业务计数不变。未知不重发。
4. verification 与 m1 commit；下一波先只读确认 W5c3w 失败事务无 Validate Receipt，再在新审批授权下执行 Validate。所有步骤不读商城源、不手工 Run。

任一审批权威、Receipt、route、Host/资源、在途、期限不足或刷新边界未知，冻结并改走正式恢复方案。
