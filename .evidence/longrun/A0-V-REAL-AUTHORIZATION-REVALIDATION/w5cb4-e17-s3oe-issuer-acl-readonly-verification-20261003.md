# E17-s3o-e｜当前发行身份与 ACL 只读审计 verification

基线 `aos-platform/m1@1c2fbe0e`、`AOS-001189`；当前库 `aos_current_preview_20260927@a0v_135`。执行本波 plan 的只读 SQL；没有迁移、GRANT/REVOKE、业务命令、Host/worker/Provider 启动。

| 核查 | 新鲜证据与结果 |
|---|---|
| 重启后服务 | `uptime`：06:39 CST 时已运行8:40；`lsof -nP`：18435、8080(PID39405)、8434(PID31986) LISTEN，18181 无；`curl /v1/health` 与 `/aip/skill-publish` 均200。当前 PID39405 是 `a0v_current_preview_http.py --signed-receipt ... --serve` 预览服务，不是正式 `--serve-limited`。|
| 权威数据 | `SELECT current_database(),current_user,version_num` → `aos_current_preview_20260927,aos_app,a0v_135`；独立全备 `aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`。所有 SQL 在 `conn.read_only=True` 下执行。|
| 五表权限 | `pg_class` + `has_table_privilege('aos_runtime',oid,...)`：`aip_skill_binding`、`aip_capability_binding`、`aip_tool_binding`、`aip_agent_registry_receipt`、`aip_assignee_resolution_receipt` 均 owner=`aos_app`、RLS=true、FORCE RLS=true，`aos_runtime` 的 SELECT/INSERT/UPDATE/DELETE 全为 true。|
| 租户与发行 | 五表 `pg_policies` 均为 `TO aos_runtime FOR ALL`，谓词仅比较 `aos.org_id`/`aos.project_id`；不验证发行身份或 Receipt 产地。Registry Receipt 有 UPDATE/DELETE/TRUNCATE append-only trigger，INSERT 仍可直写；Assignee Receipt 无用户触发器。|
| 角色 | `aos_app` 可登录、SUPERUSER、BYPASSRLS；受限登录 `aos_a0v_runtime_20260912` 非 superuser/非 BYPASSRLS，NOINHERIT 成员可 SET ROLE `aos_runtime`；`tenant_scope.apply_transaction_scope` 正是 `SET LOCAL ROLE aos_runtime`。当前角色中有预算/Guard/Network issuer，无专门 AIP Registry/Assignee Receipt issuer。|
| 根因 | `228ti2e6_module_rls.py` 曾对所有 public 表及默认未来表授予 `aos_runtime` SELECT/INSERT/UPDATE/DELETE；本库 `pg_default_acl` 仍为 `{aos_runtime=arwd/aos_app}`。`aip6_002`、`aip13_001` 的较窄 GRANT 是叠加，不撤销默认宽权限。`a0v_135` 对另一张表使用显式 REVOKE+窄 GRANT，证明需逐表收口。|

结论：应用层来源回读是必要禁入，但当前数据库角色仍可在同租户直接写造 Binding/Receipt；Registry 不可变触发器不能保证其 INSERT 来源真实。当前预览 API 的 `aos_app` 更不构成受限身份验收。**正式六 Binding、八类有效配置、Host Owner/assignment、自然首链仍缺证据，不能由本审计宣称完成。**

下一波最小施工条件：

1. 先在文件级方案中枚举 `aip_agent_registry_store.py`、`aip_assignee_resolution_store.py`、`aip_skill_registry.py`、`aip_capability_binding_service.py` 与 ToolBinding API 的合法写命令和调用身份；区分独立发行方与普通 runtime 读者。不能仅 REVOKE 后让现有服务全坏。
2. 在**隔离克隆库**写 RED：`SET LOCAL ROLE aos_runtime` 且正向租户 GUC 时直 INSERT/UPDATE/DELETE 五表应被拒；合法 Registry/Assignee 发行与合法 Binding 命令应经限定身份成功，跨租户、伪造 Receipt、重放/撤销仍拒绝。源迁移须显式撤销宽 default ACL 对目标表的实际权限，并验证重放升级与回滚边界。
3. 正式切换当前卷另波执行：先新的独立可恢复全备、ACL-faithful 全链克隆演练、零执行窗口与正式发行身份/受限 API 预检，随后迁移、服务重启与正负读回。当前库保持只读；外部身份材料缺失时仅相关实例失败关闭，继续独立代码研发。

风险：五表之外仍可能有相同默认授权遗留，需分域盘点；当前预览超级用户服务不能作为受限身份正向证据；本波只有权限只读审计，没有验证可利用性或完成隔离修复。
