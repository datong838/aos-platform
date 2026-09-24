# W5c3wR Post-Commit 审批刷新契约修复验证（2026-09-24）

方案 `0795be7f` 已实现：正式 `refresh_activation_approval` 现在仅在 committed/validated 且路由、目标 Runtime、claim gate 精确保持冻结、无目标在途时接受新的审批。原 prepared/draining 分支不变；resumed 与任何不安全状态继续拒绝。新审批仍经过完整 `_approval_authority` 校验，唯一 Refresh Receipt/幂等逻辑未改，未直接修改活体数据库或放开 claims。

专用 PostgreSQL 集成测试 `test_ecommerce_growth_cutover_pg.py`：**67 passed, 1 skipped**；新增/扩展场景确认过期旧事件在 post-commit 可用新精确审批续期并 validate，同时错误开放 claim gate 被拒绝。代码编译及 diff 检查通过。方案与实现一致，风险为新审批事件本身仍短期有效，下一波须快速且逐步完成，不能把 proposal 期限当事件期限。

下一波先生成新的正式两 checker 审批，然后以原 Prepare Receipt 在冻结窗口单次刷新；其后分别重新核对 Validate 失败边界并执行、再单独 Resume。现活体仍 operation committed、claim gate paused，不是业务成功。
