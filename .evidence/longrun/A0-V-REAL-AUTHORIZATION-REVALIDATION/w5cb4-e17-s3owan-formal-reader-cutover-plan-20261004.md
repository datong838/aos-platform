# E17-s3o-w-an｜正式 Binding Readiness Reader 角色与 ACL 切换方案（施工前）

## Rules、现时与范围

- 复习 231-4、231-9、AIP-7 22、BIND-1 31 和 s3o-w-am 的可销毁库验证。当前卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135` 只读；不能把 test-only 数据库角色/通行证搬入当前实例。
- 只读 SQL 回读：正式 `aos_aip_binding_readiness_reader` 角色数 0；EvidenceBundle、revoke event、EvalDataset 表均启用 FORCE RLS；全局 CapabilityRevision 不设租户 RLS，按全局目录合同读取。当前实例的 OIDC、Provider/Tool 签发身份仍未齐，Host/worker/Provider 保持关闭。
- 本计划只明确正式角色与 ACL 的独立切换路径。角色/ACL 是当前数据库状态改变，须新一致备份、可完整恢复的克隆、角色/表权限/RLS 正反全链和零执行窗口；没达到这些门以前不写当前库。

## 文件级施工候选与前置检查

1. `services/aos-api/aos_api/aip_binding_readiness_reader_connection.py`：冻结现有 `READINESS_READER_TABLES` 为白名单、`_require_identity` 的 NOINHERIT/NOBYPASSRLS/非 owner/非 runtime/只读/RLS/无额外表权限条件。若克隆反证发现遗漏，只改精确检查点；不放宽门。
2. `services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py`：原可销毁库已证明完整身份与撤销链。另建**从当前全备恢复**的隔离克隆演练，用原登录/当前 18 张白名单表检查正向、错租户、撤 SELECT、额外 SELECT 和写权限负向，并在事后回读原库版本/Receipt/进程未变。
3. 若克隆通过，再拟专用受控维护脚本及私有凭据文件（待定具体路径），以已核源库名/卷/备份 SHA、角色不存在、零执行窗口为入参门；事务中创建 NOINHERIT/NOSUPERUSER/NOBYPASSRLS 登录，仅授 USAGE、白名单 SELECT、每个租户表精确 RLS policy。默认只读 dry-run；失败回滚并保留诊断。不得由普通 API、请求、包代码或 migration 自动建角色。
4. 当前实例切换另行写 verification：重启加载新私有连接前核原签名安装/迁移/八工作台、Host 关闭，切换后只读回读角色、ACL、RLS 和端口。没有正式 OIDC 时仅宣称 DB reader 就绪，不宣称首链。

## 下一动作与退出条件

- 先核全备 TOC 与可恢复性、克隆可用容量、已有恢复脚本是否适配当前真实库（旧脚本若固定 `a0v_092` 不可直接运行）。然后形成精确维护命令/回滚文档，RED 先证明无角色时原连接拒绝。
- 初查：当日独立全备文件 4.0 MiB、`pg_restore --list` 5905 行且退出0；宿主可用 115 GiB、当前 Docker 数据卷 2.762 GB。TOC 可读和容量充足不等于全库恢复演练，下一步仍须隔离恢复并核表/行/Receipt 摘要。
- 2026-10-04 演练对象固定为 `colima-aos-a0v-test-only/aos-a0v-test-pg` 的新库 `aos_e17_s3owan_restore_20261004`，与当前 `colima-aos-extension/aos-a0v-recovery-pg` 物理卷分离。前检目标库不存在（0）、隔离盘可用 10.1 GiB、PG16.15、备份 SHA256 与上段一致，源库只读核 `a0v_135` 和 592 张 public 表。新库从 template0 创建，立即撤 PUBLIC CONNECT；用 `pg_restore --no-owner --no-acl --exit-on-error` 从该固定备份一次恢复。失败保留现场只读诊断，不覆盖或删除任何旧库。
- 正式库角色创建前，必须完成独立克隆全链和零执行窗口；仍保留 `a0v_135` 当前库与 Host 禁入。任何未知副作用只读对账，不重试写入。
