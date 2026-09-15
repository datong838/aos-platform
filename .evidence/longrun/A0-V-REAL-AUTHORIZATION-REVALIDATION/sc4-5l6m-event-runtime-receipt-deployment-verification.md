# a0v_058 真实部署验证

主库 aos_meta_head 已从 a0v_057 升级为 a0v_058。事件控制已进入通用精确回执账本；历史直接写权限已收敛到受控函数。24 项针对性测试通过。

- 克隆快照备份 6102147 字节，SHA256 sha256:102cfe2b05b907d0aa246d6791290b851725de6ca8d8ed7a56fdc5249dc92f7b。
- 迁移事务内 542 张既有表完整指纹前后一致：True。
- 备份至部署期间变化仅运行时租约维护表：extension_runtime_event, extension_runtime_operation, extension_runtime_outbox, extension_runtime_resource_lease；不是迁移修改。
- runtime 函数可执行，PUBLIC 不可执行，runtime 直接 INSERT/UPDATE/DELETE 均不可用。
- 首次预演因历史宽授权拒绝，保留旧克隆；第二次预演和主库事务成功。
- 未重发旧启用；下一步重新创建源窗口及 Policy 后继、精确评审后走真实启用。业务首链未完成。
