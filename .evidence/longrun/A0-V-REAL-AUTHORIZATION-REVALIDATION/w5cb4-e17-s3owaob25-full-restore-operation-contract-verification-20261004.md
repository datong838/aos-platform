# E17-s3o-w-ao-b25｜新一致全备恢复与 Capability operation 反例

## 现场与命令结果

- `m1@bd12edd1`，代码/原库迁移均 `a0v_135`；原容器 `aos-a0v-recovery-pg` 挂 `aos-a0v-recovery-pg-data`。API/Web 的 8080/8434 监听，18181 不监听；本波没有更改生产代码或重启。独占 Task Receipt `A0V-W5CB4-E17-S3OWAOB25-20261004` 已创建，230 L0 排除。
- `docker --context colima-aos-extension exec aos-a0v-recovery-pg pg_dump -U aos_app -d aos_current_preview_20260927 -Fc` exit0；私有 0700 目录 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob25-XaGvdX` 下 dump 为 4.0 MiB、SHA256 `5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`；无密码 globals SHA256 `871c59af8ff1a34da91319e15c19a92f923be9559d269481c689bd4788af61fd`。容器内 `pg_restore -l < current-full.dump` exit0，TOC 尾项为 DEFAULT ACL。宿主机没有 `pg_restore` 命令，已改用容器内二进制；第一次命令虽然 shell exit0，TOC 子命令实际上失败，未将它记作成功。
- `docker --context colima-aos-a0v-test-only exec -i aos-e17-b17-acl-pg pg_restore -U postgres --exit-on-error --single-transaction -d aos_e17_s3owaob25_restore_20261004 < current-full.dump` exit0；容器 `--network none`，独立新库，复用 b17 隔离集群/卷，不触及当前卷。源/恢复库 `a0v_135`、public 关系对象604、Binding0、Receipt6。原有24个 AOS 角色 × 604关系的有效权限摘要同为 `d8f40b9e2c2e1d895195aae02b9fa757`（14,496格）；590条 RLS 策略摘要同为 `0bf71850add6bfc2c02e7f60c6f3c855`。恢复库原始 relacl 有13个 NULL，原库0，因此只宣称有效 ACL/策略同形，不宣称原始 ACL 字节同形。
- 在上述恢复库 `BEGIN; SET LOCAL ROLE aos_runtime; SET LOCAL aos.org_id/project_id=org-org/dev-project` 后，插入 test-only Binding、仅更新 `version=version+1, updated_at=now()`，再插入 `capability_binding.evaluate` Receipt，命令顺序 `INSERT 0 1`、`UPDATE 1`、`INSERT 0 1`；回读 `version=2|operational_readiness=unknown|last_evaluated_at=NULL`，Receipt数1。`ROLLBACK` 后两张表该试验行均0。该事务只证明当前 schema 对“版本递增伪评估”没有 operation 语义约束；因执行者是 `postgres` 管理连接内的 `SET ROLE aos_runtime`，不能冒充正式独立 runtime 登录证明。b22 独立登录和 b24 test-only 守卫证据各有其边界。

## 复审结论与后续门

`AipCapabilityBindingService.create/update/evaluate` 的行写形状可区分常规路径，但 b24 的“未变 status/health 就算 evaluate”会把无评估快照的版本递增归为 evaluate。必须在独立隔离库先确定不可由普通 runtime 伪造的 operation 证据、限制非法写形状，并证明普通 Agent/Skill/Run/Handoff Receipt 兼容、旧行可读、同事务唯一配对、失败回滚；再决定 `a0v_136`。当前原库仍只读 `a0v_135`、Receipt6/Binding0、正式 issuer0；当前签名预览 Capability 写503，Host/worker/Provider关，八配置/六 Binding/Owner/自然首链待完成。不 push、不读商城源、不重放旧 Run。
