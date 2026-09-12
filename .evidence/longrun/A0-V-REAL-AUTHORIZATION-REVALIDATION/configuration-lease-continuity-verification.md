# 配置切换续租修复验证

2026-09-12，基线 462baceb。先红：配置完成续租 1 failed/6 passed；旧准备截止时间下延迟启用 1 failed/2 passed。修复后续租、延迟启用与生命周期 Owner/Scheduler 合计 43 passed；专用 18432 PostgreSQL 配置事务 21 passed（含真实配置 draining/committed 事件匹配、错租户/错代拒绝），不是主库改状态模拟。

lease_renewal 只保留有精确配置证据且禁入中的同代健康资源；ready 既有路径不改。unknown 需 committed 事件内容及 hash、当前 configRef/revision 全匹配；draining 需有效 fencing 与不可变 accepted target。资源释放、过期、权限和条件失效继续拒绝。enable 改用当前请求与租约的 deadline，保留已成功准备及资源 exact 核验。

真实故障安装仍未启用，资源已退出。下一步正常 disable 将同目标待启用请求取消并清理，正式 uninstall 后以新安装/代际重新 apply/verify/configure；禁止 reset 活跃安装或复活已释放资源。修复实际恢复验收尚待执行，不宣称本项真实闭环完成。

实际恢复第一个门已通过：新 Host v10 执行 disable succeeded，原 enable cancelled。但正式 uninstall 被 exact detached disable authority required 拒绝（无成功卸载回执）。下一波 configured-unactivated-retirement-plan.md 补真实配置后未接入的安全卸载，再恢复重装。
