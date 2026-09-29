# W5CB4 BG-00x｜今日权威备份隔离恢复与 Eval 持久 authority 文件级方案

## 前检

每日 09:04 的备份 `/Users/ddt/work/projects/ai_agent/.aos-daily-backup-20260929-oXxcWz/aos_current_preview_20260927_a0v111.dump` 是当前 `aos_current_preview_20260927@a0v_111` 只读快照，3,917,396 字节、SHA256 `e527a55cbe5fca5b32754ac08257d3d1908a895ac16b68103794d3830e868b3d`、TOC 5551；此前未全库恢复。隔离 `colima-aos-a0v-test-only/aos-a0v-test-pg` 为 PostgreSQL 16.15，12.2G 空闲，目标库 `aos_bg00x_restore_20260929` 不存在；当前源为 16.14。已有 test-only 库逐个保留，不删除/覆盖。

## 本波有界恢复演练

1. 在 test-only PostgreSQL 以 `aos_app` 创建唯一新库 `aos_bg00x_restore_20260929`，先 `REVOKE CONNECT ... FROM PUBLIC`。使用今日校验过的本地 dump，经 `docker --context colima-aos-a0v-test-only exec -i aos-a0v-test-pg pg_restore -U aos_app --no-owner --no-acl --exit-on-error -d <newdb>` 完整恢复。失败即停并保留新库/备份只读诊断，不删除、不重试覆盖，不碰 `colima-aos-extension` 当前卷。
2. 克隆与源都用 `BEGIN READ ONLY` 比对 `alembic_version`、public table/sequence/view 数量、安装 approved/四包 published/Runtime Binding 0、栖月汇 Eval Suite/Run/Report/Gate/Event 0；按仓库脚本已有计数摘要思路，对非商城源的权限/安装/制品权威表做逐表计数和 hash。只做恢复完整性，不执行商城源查询、Run、Provider、Host。
3. 只读从 `aip4_001`、`aip4_003` 与现有 `aip_eval_execution_authority.py` 收敛下一波最小持久 schema：`aip_eval_executor_identity`（双 purpose、tenant、exact ref、issuer 证书/public key、validity、Owner/approval）、append-only revocation event、`aip_eval_execution_receipt`（run/suite/case/role 唯一、claim hash、签名、输入输出 hash、issued_at）。RLS/FORCE、append-only、同租户 FK、幂等读回/冲突、当前撤销快照与报告消费必须在同事务。尚无合法 issuer/Owner，当前实例全链继续失败封闭。

## 退出与后继

本波不加 Alembic 迁移，不改变代码头 `a0v_111`，不切当前库，避免“代码头高于当前库”破坏今日最新实例。恢复演练若通过，只证明备份可在隔离 PG 恢复；不证明正式业务恢复、卸载重装或首链。下一波决定 additive 迁移与克隆演练的独立文件包；当前库迁移仍须单独备份可恢复、完整克隆链、零执行窗口并明确批准范围。保持 `m1` 单写、不 push、不读商城源、不重放旧 12 Run、不动 230 L0。

## 后继持久 schema 的精确边界（本波只冻结方案）

依据 `aip4_001` 的 `aip_eval_run` 复合租户键、`aip4_003` 的强制 RLS/append-only 模式与 BG-00w 已签 DTO，下一波需先新增独立 Eval issuer root 来源及 Owner/批准记录，不复用 OCI bundle trust root，也不把调用方传入的 root/撤销集合视为数据库权威。只有存在正式签发与审批准入时，`aip_eval_executor_identity` 才能保存 `(org_id, project_id, identity_id)`、`purpose ∈ {target,judge}`、精确 `executor_ref`、issuer/key id、证书原文及 hash、公钥、有效区间、Owner、批准凭据；必须约束同租户和唯一身份，拒绝无 Owner/批准、过期或同一公钥跨 purpose 充当双身份。

撤销用只增事件记录 identity/root 的精确键、撤销发生时间及签发/批准来源；Receipt 表以 `(org_id,project_id,run_id,case_id,purpose)` 和签名 `receipt_id` 两个唯一约束封住重放，保存身份与证书 hash、精确 suite/ref、input/output/actual/expected hash、签名原文、发生时间和规范 claim hash，并以同租户外键关联 `aip_eval_run` 与 identity。相同键相同 claim hash 只读回原 Receipt；不同 claim 必须冲突，不覆盖。所有新表按 `aos_runtime` 租户设置 ENABLE+FORCE RLS；证书、撤销事件、Receipt 为 append-only，禁止 UPDATE/DELETE/TRUNCATE。

写入顺序必须是：锁定当前同租户 Run 和身份/issuer 权威 → 在同一事务读回完整当前撤销状态与 Owner/批准 → 调用 BG-00w 纯验签并比对 exact refs/摘要 → 幂等插入双 Receipt → 在同一事务派生 Report/Gate。撤销与写入竞争须由锁或版本使后提交的一方失败封闭；若缺 root/Owner、真实 G2 内容、S3 回环或正式签发，则不允许用隔离测试密钥造当前业务正向链。迁移要在新克隆库做升降与 RLS/重放隔离测试；当前库切换另波执行，代码版本与数据库版本不允许错位启动。
