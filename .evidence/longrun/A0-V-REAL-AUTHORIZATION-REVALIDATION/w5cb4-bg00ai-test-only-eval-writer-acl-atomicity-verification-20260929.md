# W5CB4 BG-00ai｜test-only Eval writer 最小权限原子事务验证

在 `w5cb4-bg00ai-test-only-eval-writer-acl-atomicity-plan-20260929.md` 范围内，仅新增 `services/aos-api/tests/aip/test_aip_eval_writer_transaction.py`，没有生产代码/migration 或当前库写入。BG-00ah 的专属角色只存在 test-only PG。测试使用 `aos_bg00ad_schema_v2_20260929@a0v114`，org-org/dev-project 的 test-only 已签证书/Receipt；dev-org 只做 RLS 读取 canary。

1. 授权前：`has_table_privilege('aos_aip_eval_writer','aip_eval_execution_receipt','INSERT')=false`，以该角色 INSERT 触发 `InsufficientPrivilege`。这证明 BG-00ah 身份正向本身未成为写权限。
2. 只在一个 test-only 回滚事务中创建专属角色租户 policy，root/identity/revocation/Run 仅 SELECT，Receipt/Report/sidecar SELECT+INSERT，无 UPDATE/DELETE、owner 或 superuser。`SET LOCAL ROLE aos_aip_eval_writer` + 精确 org-org/dev-project GUC 后插双 Receipt、Report、sidecar；复合 FK 精确绑定同 run/case/purpose/id/claim hash。错误 target claim hash 被 `ForeignKeyViolation`；切 dev-org GUC 后 sidecar SELECT=0。全部 test-only 行、GRANT、policy 随事务回滚。
3. 第二测试故意重复 Report INSERT 触发 `UniqueViolation`，整笔事务 rollback 后 Receipt、Report、sidecar 三表均 0；无“先写 Receipt 后 Report 失败仍留半证据”。专项 `3 passed`，相邻身份/签名/reader/sidecar/预览门累计 `46 passed`，退出 0。事后独立连接回读：专属角色 Receipt INSERT=false、`bg00ai_test_writer_%` policy 数0、三表行数0。

本波证明 PostgreSQL 的最小权限/同事务**机制**可成立，尚未实现正式 writer 服务。数据库 FK 不验 Ed25519，测试使用已签 test-only 凭据；生产服务必须先在同一 authority snapshot 验签/撤销/Owner，再持久写入。当前库没有角色或 ACL 改动，正式 issuer/Owner/批准、G2 内容、真实 S3 仍缺；Skill guard/Host/worker/Provider 保持禁入。下一波 BG-00aj 先文件级设计默认关闭的签名先验+同事务 writer API，仅在 test-only PG RED；当前正式角色/策略切换另波备份+克隆+零执行窗口。
