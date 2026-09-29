# W5CB4 BG-00x｜今日备份全库隔离恢复验证

方案：`w5cb4-bg00x-backup-restore-and-authority-schema-plan-20260929.md`。基线 `aos-platform/m1@209df37e`、authority `AOS-000872`；今日 09:04 已以最新 `m1`/当前权威卷完成 PG/API/Web 重启。当前业务库只读，Host/worker/Provider 禁入。本波仅新建 test-only 演练库；未新增代码或迁移。

## 恢复命令与结果

- 当前备份 `/Users/ddt/work/projects/ai_agent/.aos-daily-backup-20260929-oXxcWz/aos_current_preview_20260927_a0v111.dump`：`shasum -a 256` 退出 0，SHA256 `e527a55cbe5fca5b32754ac08257d3d1908a895ac16b68103794d3830e868b3d`；3,917,396 字节，TOC 5551。
- `docker --context colima-aos-a0v-test-only exec aos-a0v-test-pg psql -U aos_app -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE aos_bg00x_restore_20260929 TEMPLATE template0'`：退出 0，`CREATE DATABASE`。原 test-only 库未覆盖/删除。
- 同一容器执行 `REVOKE CONNECT ON DATABASE aos_bg00x_restore_20260929 FROM PUBLIC`：退出 0；`has_database_privilege('public',oid,'CONNECT')` 为 `f`。演练库位于独立 `colima-aos-a0v-test-only`，当前库仍在 `colima-aos-extension`。
- `docker --context colima-aos-a0v-test-only exec -i aos-a0v-test-pg pg_restore -U aos_app --no-owner --no-acl --single-transaction --exit-on-error -d aos_bg00x_restore_20260929 < ...a0v111.dump`：退出 0，`/tmp/bg00x-restore.log` 0 字节。恢复失败不会留下半事务数据；本次无需重试。

## 双库只读核对

下列查询均只读执行于 `aos_current_preview_20260927` 与 `aos_bg00x_restore_20260929`，退出 0。原库/克隆的 `alembic_version=a0v_111`；public 关系计数完全一致：表 `575`、序列 `12`、索引 `1096`。安装 `org-org/dev-project` 1 条、`bundle_installation_decision.decision=approved` 1 条、`asset_bundle_version.status=published` 4 条。`extension_runtime_binding`、`extension_runtime_host_assignment`、`extension_runtime_host_identity` 均 0；Eval Suite/Run/Report、Release Gate、Publication Event 均 0。

四张非商城源权威表逐行 `to_jsonb` 规范排序聚合 MD5，原库/克隆相同：`bundle_installation` 1 条 `c5b39b87febbbb6a1555a77b1d610941`；`asset_bundle_version` 4 条 `836b5353dafb311db1384a86c0e955ad`；`asset_bundle_artifact` 209 条 `b6cf133d767052b59ef873303fbde8fe`；`aip_skill_template_revision` 37 条 `a2f204d57b62dcdcf21c6947a710be47`。MD5 仅作两个已知副本的比对摘要，备份完整性锚点是 SHA256 与 `pg_restore --exit-on-error`。

第一次读安装批准状态时错把 `bundle_installation_decision.decision` 写为 `status`，两个只读查询均退出 1；读表结构后改为 `decision` 并重查，两库退出 0。未产生数据变更。

## 结论与边界

今日备份已在隔离 PostgreSQL 完整恢复，迁移版本、公共 schema 数量与本波关注的安装/制品/禁入/Eval 权威数据相符。方案已冻结独立 Eval issuer/Owner、双 purpose 身份、撤销事件、签名 Receipt 的同租户/RLS/append-only/幂等事务边界；本波未执行迁移或测试该未来 schema。该演练不证明正式实例切换、卸载重装、真实 G2 内容/S3 回环、正式签发或自然首链。下一波须先在新演练库验证 additive 迁移、租户隔离、撤销/重放，再另波处理当前库安全切换；当前实例保持 `a0v_111`。
