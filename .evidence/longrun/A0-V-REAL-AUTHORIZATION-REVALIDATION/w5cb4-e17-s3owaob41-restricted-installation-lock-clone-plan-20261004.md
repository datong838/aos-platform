# E17-s3o-w-ao-b41｜隔离受限安装锁函数验证计划

## 方案复习与输入

- 231-3 要求安装头锁持有至最终提交，BIND-1 要求精确来源与 Binding CAS/Receipt。b40 已在 test-only PG 证明纯 SELECT/RLS 身份不能 `FOR SHARE`，Registry `(228,1)` 也不阻止安装行 `FOR UPDATE`。正式当前 `a0v_135` 无 issuer/OIDC，真实库只读。
- 既有 `tests/extension_runtime/plan_restricted_issuer_case.py` 在可销毁库临时建 `SECURITY DEFINER`、PUBLIC 无 EXECUTE、专用 BI issuer 有 EXECUTE 的精确安装锁函数，原 `PostgresInstallationStore.lock_for_bi_plan_in_transaction` 使用它；该函数仍是测试现场、不是当前正式迁移。本波复用**模式**验证 Capability 来源所需的更严 active/current/ETag/租户条件，不复用 BI issuer 身份或函数名。

## 文件级步骤

1. 仅在现有 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 的 Growth1.13 disposable active 段创建随机 test-only 非 owner/非 runtime 角色。先对尚无函数、建函数未授权两态 RED；随后 owner 建 `SECURITY DEFINER SET search_path=pg_catalog` 的独立精确锁函数，撤 PUBLIC EXECUTE，只 GRANT 给本次 role。
2. 函数要求 session_user 精确 role、org/project GUC 等于参数、SERIALIZABLE 可写显式事务；同租户安装 id/ETag 匹配且 active_revision=current_revision、当前 revision state=active，才 `FOR SHARE` 并返回 pk。任何错租户、错 id、错 ETag、无 GUC、旧代、无 EXECUTE 都拒绝，调用账号仍无安装表 UPDATE/Registry 或 Binding 写权。
3. 受限角色在同一事务先签名 Reader、再调用锁函数；另连接同安装 `FOR UPDATE` 与 Registry `(228,1)` 均须超时，提交后可取得。用隔离库专项和相邻回归、cleanup 后角色/函数不存在、静态检查验证。当前原库/迁移/生产 Reader 不修改；本波只是 test-only 能力及风险证明，不消除 b34/b37 xfail。

## 后续门

- 若克隆验证通过，下一波才设计受控 Alembic 最小迁移、正式 issuer 身份、当前卷全备/全恢复/零执行窗口切换与生产调用合同。还需原 Installation active/revoke 与 Registry 撤销并发 RED、Binding CAS/Receipt 同事务；不能把底层锁试验报成首链完成。
- 正向仅 org-org/dev-project，dev-org 零副作用；Host/worker/Provider关闭，不读商城源、不回放旧12 Run、不手工 run_definition、不碰230 L0、不 push。每日提醒到达独立完整重启。
