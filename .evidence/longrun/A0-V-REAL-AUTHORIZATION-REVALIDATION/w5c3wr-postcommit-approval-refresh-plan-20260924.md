# W5c3wR Post-Commit 审批过期恢复方案（2026-09-24）

## 现状及产品/技术方案复习

W5c3w `348fff9c` 中 Validate 被精确审批事件过期挡住，无 Validate Receipt；operation committed，九路 extension 但 claim gate paused。原 AR2 切换契约在 validate/resume 每次检查当前 ActionApprovalEvent；正式 `refresh_activation_approval` 只有 prepared/draining 可用，不能在已经 commit 的暂停窗口续期。正式 rollback 要另建 rollback 审批并反切九路，会放大影响；本波优先修复此契约缺口，但绝不弱化“当前精确审批”门禁。

## 最小代码变更

在 `services/aos-api/aos_api/ecommerce_growth_cutover.py` 的刷新入口允许 `committed`/`validated` 且未 resumed 的冻结窗口：复核九路 exact committed snapshot、目标 binding rev+1/fenced、claim gate paused、零在途；保持新审批事件的完整 `_approval_authority` 校验、唯一 Refresh Receipt 和幂等语义。prepared/draining 原路径不变；resumed、路由漂移、claims 未暂停、在途仍拒绝。目标审批仍须独立新 proposal 与两 checker，期限够覆盖 validate/resume。测试覆盖 post-commit 续期成功以及不安全状态拒绝。

## 执行与退出

1. 先修复核心与测试，专用 PG 集成测试通过并检查方案一致性；不得直接改数据库审批/claim gate。
2. 独立下一波才创建正式新审批并用精确原 prepare Receipt 调用刷新一次，取得正式 Refresh Receipt。
3. 之后才以 W5c3w 原 finalize 请求进行**新一轮显式恢复调用**；此前失败发生在事务内、无 Receipt，仍需在下一波先确认其边界，再由新审批授权执行。任何未知结果只读对账，不机械重发。

本波仅代码与测试，不在活体上直接放行。若测试无法证明恢复安全，则改走正式 rollback 方案。
