# W5CB4 BG-00ai｜test-only Eval writer 最小 ACL 与原子性试验方案

## 上位与明确不越界

BG-00ag/ah 证实当前正式库无 Eval writer，`aos_app` 为 SUPERUSER，`aos_runtime` 四张 Eval authority 表仅 SELECT；BG-00ah 的专属身份 connector 在 test-only 真 PG 通过，但目标角色尚无表写权。按 228 G2.2/231，正式 issuer/Owner/内容批准仍缺。本波只在 `colima-aos-a0v-test-only` 的 `aos_bg00ad_schema_v2_20260929@a0v114` 对 BG-00ah test role 做最小权限机制试验；不修改当前库、migration、正式凭据或生产 runner，Host/worker/Provider 与 Skill guard 不变。

## 步骤、文件和判据

1. 新增 `services/aos-api/tests/aip/test_aip_eval_writer_transaction.py`：先 RED，专属 role 目前无 Receipt/Report/sidecar INSERT 与 RLS policy，应拒绝；验证额外授予 test-only 专属 role 精确 SELECT/INSERT 和租户 RLS 后，使用 `SET LOCAL ROLE aos_aip_eval_writer` + org-org/dev-project GUC，在同一回滚事务插入两份已签 test-only Receipt、Report 和 sidecar，读回精确 FK/claim hash；故意错 hash、跨租户和 Report INSERT 失败时四者全部回滚。测试仅用 test-only 密钥与 clone 的 org-org；dev-org 仅负向可见性，不写。
2. 对专属 role 只在 test-only 库建立单独 policy：四 authority 表中 root/identity/revocation 仅 SELECT，Receipt SELECT/INSERT；Run/Report/sidecar 按实际最小 SELECT/INSERT（Run 本波预置，暂不授 UPDATE）。不改 `aos_runtime` ACL，不给专属 role SUPERUSER/BYPASSRLS、表 ownership、TRUNCATE/UPDATE/DELETE，不授正式 issuer 注册写权。
3. 若 FK、RLS 或 SQL 事务边界无法在这些最小权限下正向成立，记录具体拒绝并收口设计，不能用 `aos_app` 业务写入或放宽当前库解题。若成立，下一波 BG-00aj 才立默认关闭的签名先验+独立 connector 同事务 writer 代码，并继续用 test-only PG RED；任何当前库角色/策略变更要另波一致备份、ACL 保真克隆和零执行窗口。

本波 SQL 机制的正向不表示正式 Owner/issuer、真实 S3、Gate 消费或自然首链。计划/verification/上下文/D-waves 精确提交。
