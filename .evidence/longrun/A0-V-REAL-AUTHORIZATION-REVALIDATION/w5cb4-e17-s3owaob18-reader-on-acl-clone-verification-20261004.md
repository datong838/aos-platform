# E17-s3o-w-ao-b18｜有效 ACL 克隆 Reader 事务/独立登录验证

## 来源与 RED

- 上位 231-4/AIP-7 22/BIND-1 31 与 b17 恢复方案已复习。新目标 `colima-aos-a0v-test-only/aos-e17-b17-acl-pg`、`aos_e17_s3owaob17_acl_20261004`，容器 `--network none`、新卷，与当前原库/旧克隆隔离。原 Reader 脚本硬锁旧 b3 容器/卷/5433；`uv run python ../../scripts/a0v_e17_reader_maintenance.py --target acl-clone --admin-passfile /nonexistent` 被 argparse 以 invalid choice 拒绝，exit2。故**未扩宽**旧脚本的目标门，而在新隔离实例内以 Docker exec/本地 socket 运行精确 SQL；不把本地 trust 认证冒充私有 passfile 验证。
- 新克隆开工 `BEGIN READ ONLY`：Reader role0/policy0/Installation1/RegistryReceipt6，18表中17租户表 FORCE RLS，Capability 全局目录无租户 RLS；各 SQL exit0。当前18表只有全局 Capability Revision 10行，租户表0行。

## 事务、独立登录与恢复核验

| 门 | 证据 |
| --- | --- |
| 注入失败回滚 | 仅在新克隆以 owner 一事务创建 `aos_aip_binding_readiness_reader` 非 owner/NOINHERIT/NOBYPASSRLS 登录、18表 SELECT、前5条租户 SELECT policy 后执行 `SELECT 1/0`；psql exit3，后读 role/policy `0/0`、Installation/Receipt `1/6`，exit0。 |
| 正向最小授权 | 同一目标完整事务创建该 Reader、18表 SELECT、17条租户 SELECT policy，exit0；后读 role/policy `1/17`、Installation/Receipt `1/6`。18表 `has_table_privilege` 聚合 SELECT `18`、任一 INSERT/UPDATE/DELETE `0`，owner/runtime membership `false/false`，SQL exit0；BYPASSRLS=false。 |
| 独立会话 RLS 正反链 | 新克隆 `aip_budget_head` 原无目标行，owner 仅插入唯一 `org-org/dev-project/b18-reader-rls-test-only-20261004` 合成行，exit0。容器本地 socket 以 Reader **独立登录**而非 `SET ROLE`，`session_user=current_user=aos_aip_binding_readiness_reader`，super/bypass/inherit均false，BudgetHead/RegistryReceipt INSERT均false；全局 CapabilityRevision count10。无租户预算目标行0，设置 `org-org/dev-project` 后1，设置 `dev-org/dev-project` 后0；整个查询事务只读、exit0。`dev-org` 未写入。 |
| 清场及原库不变 | 仅删除上一步新造的 test-only 行 `DELETE 1`，目标行后读0；克隆 Reader角色/17 policy 留作验收状态。原库与克隆18 Reader＋8控制表 count/排序 JSONB 摘要重比 26/26 相等、mismatch0，SQL exit0。原库无 DDL/业务写。 |

## 方案/实现复审与下一门

- 文件级方案原想复用旧 b3 维护脚本，但 b17 克隆无网络且旧脚本精确固定5433/卷；RED 证实不能直接复用。采用新隔离实例本地 SQL，保留旧脚本强目标门，不引入生产代码/迁移/API/UI变更。旧 b3 私有 passfile 试验与本次有效 ACL 克隆独立登录共同证明两段能力，**尚未**在当前实例完成同一正式凭据链。
- 当前原库 Reader/Capability issuer role仍0、`aos_runtime` 对共享 Receipt INSERT=true，正式 OIDC/Owner/八配置/六 Binding/首链 pending。issuer 原门须失败封闭，Host/worker/Provider关。无 UI或当前生产代码变化，浏览器/前端累计回归本波不适用；真实 PG专项结果已覆盖本次变更，且未把 test-only 合成行当业务通过。
- 下一波选择当前实例正式身份来源和 operation scoped Receipt 的独立最小代码门；若需当前库 DDL，须新的正式凭据、OIDC、备份复核、零执行窗口和回滚检查。`org-org/dev-project` 唯一正向，`dev-org` 零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
