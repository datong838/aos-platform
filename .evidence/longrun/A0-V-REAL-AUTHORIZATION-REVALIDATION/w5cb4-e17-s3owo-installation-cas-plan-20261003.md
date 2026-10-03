# s3o-w-o｜独立 BI 发行身份的安装只锁 CAS 方案

## 上位约束与现状

- 231-3 要求安装头先于后续对象加锁，批准安装的 ETag/状态须与同事务 Plan/Receipt 一致；当前正式库只读，迁移和切换另波。
- 原 `PostgresInstallationStore.lock_for_transition_in_transaction` 两次 `SELECT ... FOR UPDATE`，安装变更在同一头行执行 `UPDATE`。PostgreSQL 的任一行锁子句都要求至少一列 `UPDATE` 权限，不能直接授给只读 BI issuer。
- `SignedBIPlanPreparationService.prepare` 的原非 owner 受限测试目前在安装表权限处失败，Plan/Receipt 为零。正式六 Agent/登录/发布来源仍须独立核验。

## 文件级步骤

1. 在 `services/aos-api/tests/extension_runtime/test_e17_s3owo_installation_read_lock_pg.py` 使用一次性 PG/schema 与非 owner/NOINHERIT 角色，先复现 SELECT-only 不能直接行锁；隔离创建只执行安装头锁与精确 ETag 校验的 SECURITY DEFINER 函数，固定 `search_path`、显式租户谓词、实际 `session_user`、GUC 与 `PUBLIC` EXECUTE 收权。
2. 证明正确角色/租户/ETag 可以持锁阻止合法写者改版，提交后写者通过；错租户/错 ETag/伪造角色、直接 UPDATE 失败；失败与回滚不留锁/安装变更。
3. 检查函数持锁到事务结束和当前原写者的行锁相容，不改变原 Store、真实库、安装状态或 worker。隔离协议 GREEN 后再设计原 BI 三入口接线和正式 migration，不能把探针视作正式实例授权完成。

## 风险与收口

- SECURITY DEFINER 须由受控 owner 安装，固定 schema/table/function 引用，禁止动态 SQL、隐式 PUBLIC 执行及角色可继承捷径。函数只锁、只读、返回最小字段；签名和批准验证继续用原服务。
- 隔离测试通过只证明锁协议；全 schema 原方法、RLS/表 SELECT、当前凭据、迁移克隆、零执行窗口另验。若函数无法精确约束 caller，保持失败关闭，不放宽 UPDATE。
