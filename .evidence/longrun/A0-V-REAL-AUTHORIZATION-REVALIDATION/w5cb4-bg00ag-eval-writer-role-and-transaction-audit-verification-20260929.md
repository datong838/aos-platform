# W5CB4 BG-00ag｜Eval writer 权限/事务当前事实

## 当前库只读 SQL 结果

- `pg_roles`：`aos_app` 为 LOGIN、SUPERUSER、BYPASSRLS；`aos_runtime` 为 NOLOGIN、非超级、非 BYPASSRLS；当前应用 login `aos_a0v_runtime_20260912` 为 LOGIN/NOINHERIT、非超级/非 BYPASSRLS，且是 `aos_runtime` 成员。`aos_app` 不能充当业务证据 writer，普通 runtime 不能越过正式签发边界。
- `pg_class`：`aip_eval_issuer_root`、`aip_eval_executor_identity`、`aip_eval_authority_revocation`、`aip_eval_execution_receipt` 皆为 `aos_app` owner、RLS/FORCE=true、runtime ACL=`r`。`aip_eval_case_execution_proof` runtime=`ar`，RLS/FORCE=true；`aip_eval_run`/`aip_eval_run_event`/`aip_eval_report_revision` runtime=`arwd`（继承当前默认 ACL），RLS/FORCE=true。`pg_proc` 中 proname 包含 eval 的 SECURITY DEFINER 函数数为 0；当前无 `aos_eval_%` 或 `aos_aip_%` 专用角色。
- `aip_eval_runner.py:225-309` 的 Run 建立/转态、Report、完成转态是多个连接与 commit；`aip_eval_persisted_authority_reader.py` 与 `aip_eval_report_proof_reader.py` 只在 runtime 当前事务读。当前无法仅在普通 runner 里追加 Receipt INSERT 就形成同事务证据，四表 ACL 明确拒绝。
- 已有 `aip_capability_publisher_connection.py` 展示独立文件凭据、0600/NOFOLLOW、独立 LOGIN/NOINHERIT、精确 NOLOGIN role membership 与无高权限回退模式；可借其安全形状，但**不能**复用能力发布者身份或密钥来写 Eval。正式 G2 issuer/Owner/批准来源仍不存在。

## 后继最低条件

BG-00ah 先建立**默认未配置即失败关闭**的 Eval writer 独立身份 connector 与 test-only 真实 PG 角色验证，不能在当前库造账号/填凭据。后续再按职责分离设计 issuer 注册者与 Receipt 执行 writer：须有独立非超级、非 BYPASSRLS 登录、不可管理其他角色、精确租户 RLS 和最小表权、当前审批/签名来源；同一事务写 Run 终态/Report/双 Receipt/sidecar，失败全回滚。任何数据库角色/策略迁移都需独立安全波、ACL 保真克隆、备份/零执行窗口；不得直接授普通 `aos_runtime` 四表 INSERT，也不得以 `aos_app` SUPERUSER 写业务证据。现有 runtime 对 Run/Report `arwd` 是另一个应单独审的权限债，不能因本波顺手全局重写。

审计不构成正式身份齐备或首链通过。当前 a0v114 authority/sidecar 空、Skill guard/Host/worker/Provider 继续关闭。
