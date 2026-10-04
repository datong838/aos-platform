# E17-s3o-w-ao-b38｜正式 issuer 来源 ACL 与锁顺序只读审计

## 实测对象与命令

- `m1@5d762714`、当前原卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135`。用项目 venv 调 `scripts/a0v_current_preview_http.py` 当前签名 Receipt 的 `preflight` 取得原连接参数，`psycopg` 中 `conn.read_only=True`、`SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY`；只输出角色存在性和 `has_table_privilege` 布尔值，不输出凭据或读取商城源。
- `SELECT rolcanlogin,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s`：`aos_aip_capability_issuer` → **None**；`aos_aip_binding_readiness_reader` → **None**，命令退出0。当前真实实例没有这两类正式数据库登录身份。`RegistryIssuerConnectionFactory` 要求 capability_lifecycle 精确登录前者、非 owner/非 runtime 成员；`ReadinessReaderConnectionFactory` 要求后者 read-only 且只允许指定 18 张表。现有默认服务无正式配置，不能借测试私钥/密码接当前实例。

## 来源查询的最小表面

| 来源 | 精确读取表 | 当前 `aos_runtime` 情况 |
| --- | --- | --- |
| 安装唯一 active/current 候选与原锁 | `bundle_installation`、`bundle_installation_revision`、`bundle_composition`、`bundle_composition_lock` | 四表 RLS=true/force=true；runtime SELECT=true、UPDATE=true |
| 当前 Registry 快照与签名证据 | `asset_bundle`、`asset_bundle_version`、`asset_bundle_artifact`、`asset_bundle_evidence` | 四表 RLS=false；runtime SELECT=true、UPDATE=true |

表名由 `_read_unique_active_in_transaction`、`load_stored_lock` 和 `_SNAPSHOT_QUERY` 逐项导出，八表的 `pg_class`/`has_table_privilege('aos_runtime',...)` 只读查询退出0。`aos_runtime` 持有 UPDATE，且 issuer 连接工厂明确拒绝 runtime 成员；不可用它冒充最小权限最终事务登录。正式 issuer/Reader 角色不存在，故它们的当前表 ACL 和正向登录均无从验收。

## 锁序与未满足的并发门

- 原 `InstallationStore.lock_for_cas` / `lock_for_transition_in_transaction` 对 `bundle_installation` `FOR UPDATE`；`load_active_baseline_in_transaction` 用 `FOR SHARE`。Registry 状态转换在 `RegistryStore` 先取 `pg_advisory_xact_lock(228,1)`，再锁对应 bundle/version 行；`RuntimeReleaseRevalidator.revalidate_in_transaction` 也取同一 advisory 锁后读 `_SNAPSHOT_QUERY`。
- b37 内部来源 Reader 当前 **不**锁安装行，公开包装是 read-only 事务不能做 `FOR SHARE`；AIP 激活最终事务未调用该 Reader。正确正向尚需精确安装行锁、Registry advisory/状态重验、Binding CAS/Receipt 同一 issuer 事务，且分析多候选/新插入时的 SERIALIZABLE 行为与死锁顺序。只读视图或已持有 advisory 锁均不能独自证明此门。

## 结论与恢复入口

- 本波完成源表/权限/锁序的只读合同审计；当前正式低权身份不存在，不能在当前真实库做合法 issuer 正向或声称 b34/b37 strict xfail 消除。无生产代码、迁移、当前库写；未用 owner/test-only 身份伪造首链。
- 下一波先在已恢复的独立克隆/可销毁完整迁移库验证最小非 owner 发行角色对八表精确 SELECT、安装行锁与 Registry 撤销锁的正反例；若需正式 ACL/RLS/issuer 工厂变动，文件级方案、RED、备份/完整恢复、零执行窗口另立切换波。当前实例继续禁入，Host/worker/Provider关，Goal active。
