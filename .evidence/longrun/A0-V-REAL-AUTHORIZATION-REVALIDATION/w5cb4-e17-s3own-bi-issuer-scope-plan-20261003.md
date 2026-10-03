# W5CB4 E17-s3o-w-n｜Tool 来源缺口与 BI Plan 独立事务身份第一切片

基线 `m1@c3d67dbb`、Authority `AOS-001225`。已复习 231/231-2/231-3、W-L20、s3o-s 宽 ACL 审计、s3o-w-j 原 BI prepare RED、原 `apply_asset_transaction_scope`/Plan 服务和当前签名树。当前安装的四个已签 bundle 未发现可核验 ToolDefinition；`wave_ext.list_tools` 混合内存/函数/动作/Capability 展示项，独立内存 ToolRegistry 可注册代码，均非带批准/安装引用的 durable Tool 来源。正式 ToolBinding issuer/RegistryReceipt 不在来源不明时造假；此缺口限于该实例。依 D-wave s3o-w-n 的替代路径，先解 BI Plan 非 owner 发行者首个事务身份冲突。

## 目标与边界

原 `SignedBIPlanPreparationService.prepare` 同事务先调用 `apply_asset_transaction_scope`。TI6 policy 已采纳时，辅助函数对非 `aos_runtime/aos_app` 登录无条件 `SET LOCAL ROLE aos_runtime`；前波真正非 owner/NOINHERIT Plan issuer 因没有 runtime 成员资格最先 SQLSTATE42501，尚未到安装锁/权限和原 Plan 发行。本切片允许**不具 runtime 成员资格的登录保留自身 DB 身份、只绑定事务级双租户 GUC**；权限仍完全由原表 GRANT/RLS 决定，绝不授予 runtime 成员、BYPASSRLS 或 owner。原 runtime 成员连接继续原 `SET LOCAL ROLE` 行为；未改变安装状态机、Plan 请求、公共 API 或当前库 ACL。

## 文件级步骤

1. 先在 `services/aos-api/tests/asset_registry/test_adopted_transaction_role.py` 加隔离 PG 真实非 runtime 成员登录 RED：调用原 helper 应保留 current/session_user、绑定事务级 `aos.org_id/project_id`；无额外表权限时安装读取仍拒绝，提交后 GUC 清空。原 runtime 身份行为仍由既有测试覆盖。
2. 仅改 `services/aos-api/aos_api/asset_registry/tenant_transaction.py`：已采纳 TI6 且连接既非 runtime/aos_app 时，先核 `pg_has_role(current_user,'aos_runtime','member')`；有成员资格走原 `SET LOCAL ROLE`，无成员资格只设事务级 GUC。不要额外 GRANT 或禁用 RLS。以原完整签名隔离测试发现 BI prepare 的下一个精确依赖；若是安装行锁，在独立 PG 另证 SELECT-only 发行者 `FOR UPDATE` 是否需 UPDATE 权限，禁止简单授予安装表 UPDATE。缺权限/来源时仅该路径失败关闭，记录零 Plan/Receipt 增量，不把首个门移除等同 BI 正向。
3. 专项及原 signed full-schema/Plan 相邻回归、py_compile、目标 diff check。若实际服务路径需要更多最小 ACL/Issuer 接线，先重新按源码/SQLSTATE列文件级步骤再实现。无前端改动，浏览器页面沿用上一轮最新栈禁入证据；当前真库只读，不改 migration/凭据/Host。

## 退出条件与后续

本波可先以独立事务身份与下一精确拒绝点落证，不能宣布 BI Plan 发行 GREEN。后续要在隔离 PG 补安装锁、当前权限、六 active Agent、原 Plan head/revision/Receipt 的真实同事务正反、幂等/CAS/回滚、runtime SELECT-only；正式发行登录/ACL 迁移及当前库切换仍需新备份、全链克隆、零执行窗口。Tool durable sourceRef/批准安装引用与专用 issuer/RegistryReceipt 合同另列下波，不以展示卡或内存注册充数。
