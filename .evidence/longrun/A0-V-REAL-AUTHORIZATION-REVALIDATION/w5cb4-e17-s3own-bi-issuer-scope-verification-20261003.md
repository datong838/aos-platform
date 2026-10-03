# E17-s3o-w-n｜独立 BI Plan 发行者事务身份第一切片

基线 `m1@c3d67dbb`、Authority `AOS-001225`。按同前缀文件级方案先读 231/231-2/231-3、W-L20、s3o-s、s3o-w-j、原事务辅助函数/BI 服务与签名树。当前签名安装四 bundle 的 manifest 和文件名无 durable ToolDefinition；当前 `wave_ext` Tool 列表由内存/函数/动作/Capability 展示项组成，不能作为正式 ToolBinding 来源。Tool 独立 issuer/RegistryReceipt 暂无合法来源，不做表面发行。

| 门 | 本次证据 |
|---|---|
| RED | `uv run pytest -q --disable-warnings --tb=short tests/asset_registry/test_e17_s3own_bi_issuer_scope_pg.py` → exit1，1 failed；非 owner、非 runtime 成员真实登录在原 `apply_asset_transaction_scope` 被 `SET LOCAL ROLE aos_runtime` SQLSTATE42501 拒绝。 |
| 最小改动 | `asset_registry/tenant_transaction.py` 对 TI6 已采纳且非 runtime/aos_app 的真实连接先核 `pg_has_role(current_user,'aos_runtime','member')`。成员沿用原 `SET LOCAL ROLE`；非成员保留原登录身份，只设置事务级双租户 GUC，异常 membership 结果拒绝。无 GRANT、RLS、迁移、HTTP 或安装状态变更。 |
| 受限权限正反 | 一次性 PG 非 owner `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS`：自身 current/session_user 保留，GUC 正确，rollback 后清空；无授权的 `bundle_installation` SELECT 拒绝。只授 SELECT+同租户 RLS policy 后，普通 SELECT 可执行，`SELECT ... FOR UPDATE` 仍 SQLSTATE42501。测试角色/策略回收后残留0。 |
| 原签名链 | 使用当前签名预检取得连接只为创建/销毁 `aos_test_*_ti4_test`，本地 Growth1.13 签名回执运行原 `test_growth_signed_installation_full_schema_pg.py` → exit0，1 passed。`SignedBIPlanPreparationService.prepare` 的首个拒绝已从 `SET ROLE` 推进到 `bundle_installation` 权限，Plan head 与 `bi_responsibility_plan.prepare` Receipt 仍0；原 generic Plan 测试继续通过。更新原测试精确预期，不宣称 BI prepare 正向。 |
| 相邻 | 单独测试会话 `39 passed/8` 个已有严格 xfailed，exit0；签名全链单独测试会话 `1 passed`，exit0。把两套放同一 pytest 会话曾因已有固定 AgentInstance fixture 同 ID 冲突而 `1 failed/39 passed/8 xfailed`，分开运行后各自 GREEN；未改变业务代码以掩盖测试隔离问题。`py_compile`/目标 diff check exit0。 |

复审：原 `PostgresInstallationStore.lock_for_cas/lock_for_transition_in_transaction` 对 `bundle_installation` 用 `FOR UPDATE`。给 BI issuer 宽表 UPDATE 会允许变更安装行，不能作为下一步捷径。下一波需在隔离库设计只锁不改的精确安装 CAS 合同，并证明既有状态转换写者并发协调；再补最小 SELECT/RLS 与当前权限读取、六正式 Agent、同事务 Plan/Receipt 正反。不能把本切片、test-only Growth1.13 或页面200算当前正式安装与自然首链。当前真库只读、Host/worker/Provider关、org-org/dev-project 唯一正向，不读商城源、不重放旧12Run、不手工 run_definition、不触碰230 L0、不 push。
