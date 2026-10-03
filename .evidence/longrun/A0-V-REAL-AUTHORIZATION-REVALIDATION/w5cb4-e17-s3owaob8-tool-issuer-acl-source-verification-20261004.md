# E17-s3o-w-ao-b8｜正式 Tool 来源与发行 ACL 当前负证据

## 只读现场与代码合同

- 2026-10-04 原权威卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135`，`BEGIN READ ONLY` 查 `pg_class/pg_policies/has_table_privilege`，命令 exit0：`aip_tool_binding` owner=`aos_app`、RLS/FORCE=true/true、`aos_runtime` SELECT/INSERT/UPDATE=true/true/true；`aip_agent_registry_receipt` 同为 owner=`aos_app`、RLS/FORCE=true/true、runtime SELECT/INSERT/UPDATE=true/true/true，租户 policy 指向 `aos_runtime`。runtime 非 owner 成员、非 super/BYPASSRLS、NOINHERIT。Receipt 的 append-only UPDATE/DELETE 与 TRUNCATE 两个 trigger 均 enabled；它们不阻止新 INSERT，所以不能以触发器推断 Tool Receipt 不可伪造。
- 仓库初始迁移 `aip13_001_assignee_resolution.py` 向 runtime 授 ToolBinding SELECT/INSERT/UPDATE；`aip6_002_registry_receipts.py` 向 runtime 授共享 Receipt SELECT/INSERT。现库 Receipt ACL 为 `aos_runtime=arwd`，比该初始迁移更宽；本波只记录当前有效 ACL，未断言扩权来源。共享 Receipt 还有合法的 Agent/Skill/Capability/Plan/Content operation；直接撤销所有 runtime INSERT 会破坏现有路径，必须按 operation 与真实 DB session 分流。
- 当前签名四制品已在 b5 精确查为无 ToolDefinition；本轮仓库限定文件名搜索也未找到正式 ToolDefinition 制品。`UpsertToolBindingRequest` 无 signed exact ref/installation epoch，原 Store 普通连接直写 ToolBinding 且独立 commit；路由 `_require_role` 允许 admin/executor/aip_executor，不能把 API 角色当 DB 专用 issuer。`aip_registry_issuer_connection.py` 的现有 agent/skill/capability 工厂反而把 ToolBinding 写权列作 cross-domain 禁项，不能冒用。
- b6 原 active 无来源 writer 与同事务 Receipt 两个 strict xfail 本轮按准确文件重跑：`2 xfailed`、exit0。初次误用不存在的 `tests/aip/test_tool_binding_issuer_receipt_red.py`，pytest exit4 未收集；用实际 `test_e17_s3or_tool_binding_source_receipt_pg.py` 复跑，不把 xfail 算 GREEN。

## 判定与下步

正式 ToolBinding 正向需要同一签名 ToolDefinition exact ref、批准 Owner/安装 epoch、独立 Tool issuer 登录、同事务 ToolBinding+RegistryReceipt、runtime 不可伪造 Tool operation，以及幂等/CAS/错租户/撤销并发。当前原实例上述来源与身份均未齐，不能启 active ToolBinding/Host。b8 本切片是**当前权限与来源负证据及协议修订**，没有生产代码、迁移或当前库写入，Last GREEN 不应升级为正式 Tool 发行。

下一安全切片按 D-waves 已登记替代路径转 Eval/License/Reader 的合法来源或独立代码门；Tool 公共协议先完成 signed source 与 DB operation 分流复审，再在 test-only PG 做正反链。不得仅追加应用层 Receipt、直接全表 REVOKE 或用当前无来源制品造正向。Goal active，真库只读，Host/worker/Provider关；org-org/dev-project 唯一正向，dev-org 零副作用，不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0、不 push。
