# E17-s3o-w-an｜当前 a0v_135 全备独立恢复演练（阶段证据）

按同名前缀 plan 在写前复习 231-4、231-9、AIP-7 22、BIND-1 31，并固定源/目标身份。目标是验证正式 Reader 切换所依赖的当前库备份可恢复；本记录不表示当前 Reader 角色、OIDC、Host 或首链就绪。

| 检查 | 命令/事实 | 结果 |
| --- | --- | --- |
| 隔离身份 | `docker --context colima-aos-a0v-test-only inspect aos-a0v-test-pg`、`colima list`；目标 `aos_e17_s3owan_restore_20261004` 预检 count=0 | 独立 PG16.15、独立卷，测试盘可用10.1 GiB；与 `colima-aos-extension/aos-a0v-recovery-pg` 权威卷不同，exit0 |
| 原全备 | `shasum -a 256 aos-recovery/.aos-current-backup-20261003-1952-135/current-full.dump` | `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc`，exit0；此前 TOC5905 |
| 全库恢复 | 测试 PG `CREATE DATABASE ... TEMPLATE template0`、立即 `REVOKE CONNECT ... FROM PUBLIC`；`docker --context colima-aos-a0v-test-only exec -i aos-a0v-test-pg pg_restore -U aos_app --no-owner --no-acl --exit-on-error -d aos_e17_s3owan_restore_20261004 < current-full.dump` | 创建、REVOKE、完整 pg_restore 均 exit0；未覆盖旧库、未删除任何库/备份 |
| 元数据一致 | 源与克隆 `BEGIN READ ONLY` 查 `alembic_version`、`pg_tables`、sequences、views | 都是 `a0v_135`、592/11/0，exit0 |
| 精确 Reader 输入 | 对 `READINESS_READER_TABLES` 18 张表，源/克隆分别只读计算 `count(*)` 与按行 JSON MD5 排序的聚合 MD5 | 18/18 匹配，命令 exit0；CapabilityRevision 10 行，其余17张本快照0行 |
| 安装/控制面 | 同法比较 `bundle_installation`、revision/event、composition_lock、asset_bundle_version、aip_agent_registry_receipt、aip_capability_binding、extension_runtime_host_command_receipt | 8/8 匹配，命令 exit0；行数依次 1/3/3/1/4/6/0/0 |
| 源不变 | 源 `BEGIN READ ONLY` 查 `a0v_135` 与 `aos_aip_binding_readiness_reader` 角色数 | `a0v_135`/0，exit0；8080 和8434 LISTEN，18181 无监听（合并 `lsof` 对不存在端口返回1） |

`--no-acl` 意味着本次先证明物理数据恢复，不代表恢复了正式权限。后续只在隔离克隆验证 NOINHERIT/NOBYPASSRLS 独立角色、18表 SELECT、租户 RLS、撤权/额外授权负例，再形成当前库维护 SOP；当前库仍只读，Host/worker/Provider 关闭。未读商城源，未重放旧 Run 或手工执行 Run。

**2026-10-04 s3o-w-ao-b2 计数更正**：上表“11序列”为本记录统计误差。后续分别对当前源与独立恢复克隆只读列出 public `pg_class.relkind='S'` 名称，双方12/12同名；`pg_sequences` 双方也都是12。此更正不涉及 DDL/数据写入，后续维护预检以双端实读12为门值，详见 s3owaob2 verification。
