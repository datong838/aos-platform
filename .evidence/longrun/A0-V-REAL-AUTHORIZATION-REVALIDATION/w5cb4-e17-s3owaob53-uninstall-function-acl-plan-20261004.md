# b53 文件级方案｜正式卸载函数 ACL 与唯一迁移排程

## 上位与最小点

- 231-3 保留 runtime active→uninstalled 的原窄 Store，但须经 RuntimeOperation 停用排空和资源释放，且正式身份/Receipt 同事务。`ar2_018` `extension_runtime_uninstall_commit_ar2_018` 只向 `aos_app` 授 EXECUTE；标准租户连接会 `SET ROLE aos_runtime`，当前两角色无继承。
- b52 临时测试 GRANT 仅在可销毁 PG 中用于暴露缺 Binding 语义漏洞，清理后不留权限。不能把它带到当前实例。
- 现有下一头唯一 `a0v_136` 已同时承载 Capability operation/Receipt guard、受限安装锁函数的待定设计；正式可信 evaluate 协议尚未冻结。不得为修本 ACL 单独抢占136，使最新代码/当前卷135漂移。

## 本波步骤

1. 只读核验 m1 Alembic head、当前权威库版本、`pg_has_role`、两角色 `has_function_privilege`，仅输出布尔值及库身份，不输出凭据。
2. 对照函数 SECURITY DEFINER 校验的 `session_user`、应用 `current_user`、租户 GUC、RLS、Receipt 约束；明确未来最小授权只能给用于运行卸载的受限执行身份，且必须证明直接 DML/错租户/错 actor/未排空/重放仍拒绝。
3. 本波只立迁移前置，不写136或当前库；后续先在完整 signed disposable 克隆做正反权限/角色/资源义务 RED，再统筹唯一迁移和独立备份/全恢复/零执行窗口。

## 判据

只读事实和排程经验证登记，当前运行 Host 保持关闭；不声称合法卸载可用，也不把 b52 负门当正式首链通过。
