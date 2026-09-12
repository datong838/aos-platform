# 管道控制增量部署

2026-09-12，基线bb737f14。用户已授权本地m1全权推进产品目标；保持不push、230 L0挂起及既有dispatch权限事项独立。此波仅新增审批历史，不批准业务执行。

1. 状态门：memory-status强投影CURRENT、memory-validate GREEN；现有A0-V Lease排除共享迁移，因此为本次独占colima-aos-extension/aos-a0v-recovery-pg/aos_meta_head上a0v_021→a0v_023两项精确增量登记单独m1 Lease。不扩大到生产库、旧Docker磁盘或其他业务变更。
2. 先修新预检的秘密传递：runtime_connections.py增加可选AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE，仅0600、自有、非链接的现有Host身份文件；内存读取运行/网页DSN比对并复用原无权限切换连接。原环境URL调用兼容。预检脚本只设置路径、包根和信任根，不再将凭据放环境。文件内容不日志、不提交。测试路径/权限/格式/跨身份检查。
3. 备份目标库至独立受保护目录，记录hash/大小；隔离命名克隆恢复备份，验证恢复后的a0v_021，执行且仅执行a0v_022/023，检查原核心计数不变、新表为空、FK/RLS/immutable合同和aos_runtime权限。保留备份，不触碰旧Docker.raw/恢复文件。
4. 正式迁移前再次核对当前HEAD、a0v_021、目标库身份、两份迁移hash、无其他持有者，并持有migration advisory lock；同事务添加两表与Alembic版本。失败回滚，不强行stamp、不降级删除表。完成后只读检查真实表为空、配置/安装/源/图未变、Host连续性、页面API健康。
5. 审批/执行另起下一波：通过现有运行身份的当前服务生成Selection与Control，不绕开权限；正式数据流仍经ScheduleRun和Ingress，不以迁移成功宣称经营链成功。

新增部署脚本前另列具体文件、固定目标/预期基线/停止条件和测试。当前步骤尚未进行真实迁移。

具体部署工具：scripts/a0v_pipeline_control_deploy.py，仅prepare/apply两阶段；固定主库aos_meta_head与克隆aos_pipeline_control_20260912_ti4_test，固定colima-aos-extension/aos-a0v-recovery-pg。使用现有容器连接工厂，在进程内把已验证参数传给Alembic Config（不放环境、不输出DSN），调用command.upgrade到a0v_023而非stamp。prepare保留完整ACL/owner的pg_dump于0700目录/0600文件，新建独立克隆且拒绝覆盖既有库，撤销克隆PUBLIC CONNECT、不启动API/Host，再验证恢复与精确迁移。apply要求准备证据/备份/迁移hash一致及两Lease有效，持有数据库advisory lock；用有限lock_timeout/statement_timeout执行两份迁移。数据库行只输出计数和摘要，驱动/工具错误只输出安全类型与位置，备份不提交。

隔离预检10:49Z发现原库default privileges会给新表UPDATE/DELETE（不可变触发器仍在，但不符合最小权限）。两项遗留默认权限测试已复现。a0v_022/023尚未部署主库，补显式REVOKE ALL FROM PUBLIC,aos_runtime后仅GRANT SELECT,INSERT，并抽出各迁移restrict_history_permissions供该已创建且为空的隔离克隆重复收口。保留首次失败证据、原备份和克隆，不删除重建。resume-prepare仅允许主库仍a0v_021、克隆a0v_023、9张关键表摘要完全相同、两新表为空时调用这两个权限函数；重验后记录这是权限修复后的验证，不冒充首次无失败通过。
