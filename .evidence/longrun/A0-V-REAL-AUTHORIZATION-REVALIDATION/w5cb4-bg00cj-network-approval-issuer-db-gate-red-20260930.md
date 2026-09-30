# W5CB4 BG00cj｜网络审批 DB 门克隆 RED

依据同名文件级方案。当前权威库只读，RED 只在既有 `aos_bg00bx_cutover_testonly_20260930@a0v_117` 克隆内运行；无当前库 DDL/DML、无外部效果。

## 现行权限与结构

当前库只读查询 `pg_roles`、`information_schema.role_table_grants`、`pg_trigger`：`aos_runtime` 是非超管、非BYPASSRLS、NOINHERIT；它对 `aip_action_approval_event` 有 SELECT/INSERT/UPDATE/DELETE；网络 ApprovalEvent 与 Proposal 表无非系统业务触发器。当前 API 用 `aos_app` 超管，故仅以 API 代码检查不能给 DB 门作正面证明。

## 克隆 RED（退出码均为0，表示被测试的非法操作成功，安全预期失败）

1. `psql -U "$POSTGRES_USER" -d aos_bg00bx_cutover_testonly_20260930 -At`：`BEGIN; SET LOCAL ROLE aos_runtime; SET LOCAL aos.org_id='org-org'; SET LOCAL aos.project_id='dev-project';`。身份回读 `session_user=aos_app|current_user=aos_runtime|org-org|dev-project`。对所有栖月汇网络 Proposal 关联的 `aip_action_approval_event` 执行 `UPDATE ... SET reason=reason RETURNING ...`，输出 `UPDATE 8`，然后 `ROLLBACK`。预期普通 runtime 无法 UPDATE 网络 Event，故为 RED。
2. 相同角色与 tenant 的另一事务，`UPDATE aip_action_proposal SET proposal_hash=repeat('0',64) WHERE action_type_id='aip_activate_network_policy' AND org_id='org-org' AND project_id='dev-project'`，输出 `UPDATE 5`，随后 `ROLLBACK`。事后 `SELECT count(*) ... proposal_hash=repeat('0',64)` 返回0。预期网络 Proposal 核心哈希不可改，故为 RED。

两次使用旧克隆已有的网络行，未造新 maker/checker、未读业务源、未越租户；执行成功只能证明普通 runtime 可越过服务层直接篡改证据，不能作为可用审批。后续绿色门必须在独立克隆证明普通 login/SET ROLE/GUC 都不可冒充专用签发者，合法签发路径仍保留真实 OIDC 人类 checker、幂等与同事务绑定。当前实例缺正式 IdP/第二人，继续禁入。
