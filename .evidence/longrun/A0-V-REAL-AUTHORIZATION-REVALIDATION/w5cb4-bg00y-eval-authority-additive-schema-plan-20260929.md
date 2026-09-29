# W5CB4 BG-00y｜Eval 正式 authority 空表迁移文件级方案

## 前检与目标

主计划 `231` 的 A1 首链要求真实 Eval、租户隔离、持久幂等；`231-1` 的 SDK 权限只取签名 allowlist 与当前批准交集。`aip4_001` 已有同租户 EvalRun 键、`aip4_003` 有强制 RLS 与 append-only 先例；BG-00v/w 是独立 Eval issuer、Target/Judge 签名 Receipt 的纯合同；BG-00x 已把今日 `a0v_111` 备份完整恢复到隔离库。当前正式 issuer/Owner/G2 内容与真 S3 均缺，故本波只建**默认空、运行角色不可写**的 authority 表，绝不造当前业务正向身份/Receipt。

## 精确文件与最小合同

1. `services/aos-api/alembic/versions/a0v_112_eval_execution_authority.py`：`down_revision=a0v_111`，仅新增四张空表：
   - `aip_eval_issuer_root`：同租户 `(org_id,project_id,issuer_id,key_id)`，专用 `eval-execution` purpose、公钥/有效区间、非空 Owner/批准来源、证书/来源 hash。不可使用 OCI bundle trust root；没有任何默认行。
   - `aip_eval_executor_identity`：同租户 identity、purpose `(target|judge)`、精确 ref、issuer 复合 FK、证书原文/hash、公钥及 hash、有效区间、非空 Owner/批准来源。租户内公钥 hash 唯一，且 `(org,project,identity_id,purpose,certificate_hash)` 供 Receipt FK 精确关联。
   - `aip_eval_authority_revocation`：identity 或 root 二选一的同租户复合 FK、撤销时间/Owner/批准来源；唯一 subject，追加式且不允许解除覆盖。
   - `aip_eval_execution_receipt`：同租户 `aip_eval_run` 和 identity 复合 FK，`(org,project,run_id,case_id,purpose)` 与签名 receipt ID 两个唯一键；保存 exact suite/ref、claim/输入/输出/actual/expected hash、发生时间、签名原文，禁止覆盖不同 claim。
   四表 `ENABLE/FORCE ROW LEVEL SECURITY`，仅 `aos_runtime` 租户策略可读；不给运行角色 INSERT/UPDATE/DELETE/TRUNCATE。使用 `guard_aip4_append_only()` 防 UPDATE/DELETE/TRUNCATE；迁移反向不得默认删持久证据，需 fail-closed 升级/回退裁决。
2. `services/aos-api/tests/aip/test_aip_eval_authority_schema.py`：先 RED 无 `a0v_112`，后在**新** test-only 克隆 `aos_bg00y_migration_20260929` 检查四空表、RLS/FORCE、运行角色不能写、隔离 superuser 机制行的同租户 FK/双唯一键/追加式拒绝、撤销唯一约束、跨租户与跨 purpose 拒绝。测试行仅存在于隔离克隆或回滚事务，不作正式业务证据。
3. `.evidence/.../w5cb4-bg00y-*-{plan,verification}-20260929.md` 记录 RED/迁移/回归/当前库差异、并更新 docs 300 与 D-waves。

## 迁移执行和验收边界

先验证今日备份 SHA256，另建唯一 test-only 库并 `REVOKE CONNECT FROM PUBLIC`，用 `pg_restore --single-transaction --exit-on-error` 全量恢复。克隆从 `a0v_111` 升到 `a0v_112`；核对四表默认空、当前安装/制品摘要与旧库不漂、角色权限；对冲突/租户隔离运行负例。当前 `aos_current_preview_20260927` **不迁移**；迁移代码提交后运行中的 `a0v_111` API 必须保持原进程，不允许重新以更高代码头启动并报告“最新”，待独立下波取得新备份、克隆全链、零执行窗口再切。Host/worker/Provider 继续关闭。

## 退出条件和风险

RED 明确指向缺 schema；新迁移文件 hash、测试、`alembic` 头、克隆版本与角色禁入均有可回读输出。纯表结构无法验证证书签名、当前撤销时序或同事务 Report/Gate 消费，后继必须接 BG-00w 验证器与正式 issuer/Owner 读取权威；在此之前运行角色无 INSERT，生产 Skill 保持失败封闭。缺任一上述结果，本波不称 GREEN；不碰商城源、旧 12 Run、dev-org、230 L0，不 push。
