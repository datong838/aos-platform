# b49｜撤销并发与 SERIALIZABLE 快照负门（文件级计划）

基线：`m1@a516acc0`、AOS-001307，当前真库135只读。本波仅完整 signed Growth1.13 disposable PG/OCI 克隆。

## 先读事实

- 231-3 安装锁顺序与 BIND-1 当前依赖、CAS/Receipt 要求仍适用。`RegistryStore.transition_version` 先取 advisory `(228,1)`，再锁 bundle/version/依赖/证据行，更新状态和生命周期事件并提交。
- b47/b48 test-only 命令在 SERIALIZABLE 事务中先安装行 `FOR SHARE`，再等 advisory，随后普通 SELECT Registry exact `published`。PostgreSQL 事务快照可能在等待前固定；若撤销在等待中提交，普通 SELECT 可能读旧 published。不能只凭共同 advisory 断言安全。

## RED 与最小修复

1. 在 `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py` 加独立 test-only `AOS_B49_CONCURRENT_REVOKE=1` 模式：第1连接锁 Growth version 行；正式 `RegistryService.revoke` 在第2连接获得 advisory 后等待行；低权评估第3连接先锁安装再等待 advisory；第1连接放行，使 revoke 提交；评估继续。以 PG 锁状态而非固定 sleep 判定阶段，并给线程/SQL 有界超时及 finally 清理。若评估写第二 Receipt 为 RED。
2. 修补只在 test-only 函数当前 release 查询增加 row lock/recheck，使旧 SERIALIZABLE 快照遇到已提交版本变化时失败关闭；若同事务无法安全做到，记录反例并重设计事务隔离/锁顺序，不放行 available。确认 Binding/Receipt 全回滚、正常 signed 路径仍通过。
3. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 仅增 b49 测试模式分流；先跑 RED 再改 SQL。相邻 b37/b45/revalidator 回归、语法、diff check 与 verification。正式 evaluator 签名字节/信任根、八类依赖和正向可用态仍独立待证；不得由本波 blocked-only 结果启 Host。

当前库无迁移/写入，Runtime Host/worker/Provider 关，不读商城源、不碰旧 Run/230 L0、不 push。

实施中发现：普通 `SELECT` 在等待 advisory 后确实读到旧快照并写 Receipt，RED 为 `AssertionError: applied`。`FOR SHARE` 需 UPDATE 权限；仅给 test-only NOLOGIN definer 的 release `status` 列级 UPDATE，低权调用者没有该权限。正式身份不能直接照搬这个权限设计，需在生产迁移前独立审查。
