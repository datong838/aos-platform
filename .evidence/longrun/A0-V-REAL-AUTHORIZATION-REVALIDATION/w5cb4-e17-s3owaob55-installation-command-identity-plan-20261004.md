# b55 文件级方案｜安装命令可信连接与运行角色分离

## 上位与现场

- 231-3 保留不可变 Installation/CommandReceipt，同事务终结运行卸载；运行 worker 无权自行终结。b54 在 disposable PG 验证 app-role 正向、aos_runtime 函数直调拒绝；b53 当前库只读核验 aos_runtime 无 EXECUTE，aos_app 有 EXECUTE。当前库 a0v_135 只读，Host/worker/Provider 关闭。
- `control_wiring.build_installation_service` 和 RuntimeControlPlane 均构造默认 `PostgresInstallationStore()`；`installation_store.execute_idempotent` 在唯一连接上绑定租户、取幂等锁、重验、调用 handler、写 CommandReceipt。`db.connect` 使用当前通用 DSN，TI6 的 `apply_asset_transaction_scope` 可切 aos_runtime。因此合法 active 卸载调用 `ar2_018` 时 ACL 失败；不能给运行角色 GRANT EXECUTE。
- 2026-10-04 16:00 左右现场 PG `aos-a0v-recovery-pg` 与 18435、API 8080、Web 8434 在；`/v1/health`、`/v1/ready`、发布页 200，18181 无监听。页面与首链是否通过必须另验，HTTP 200 不等于业务通过。
- 当前库只读角色核验：`aos_app` 实为 LOGIN/SUPERUSER/BYPASSRLS，故即使有函数 EXECUTE，也被 `ar2_018` 的 `session_user` 非高权检查拒绝。它只能是当前预览与迁移账号，不能直接当正式安装命令身份。PG16 无卷隔离库在同一事务中验证 `GRANT aos_app TO 专用低权角色 WITH INHERIT FALSE, SET FALSE` 可令 MEMBER=true、USAGE=false、SET=false 后 ROLLBACK；这是待审候选机制，不是已授权的正式登录或完整命令链。

## 文件级步骤

1. `asset_registry/control_wiring.py`、`installation_store.py`、`tenant_transaction.py`、`db.py` 与 `ar2_018`：先画出当前连接、session_user/current_user、租户 GUC、函数 ACL、Receipt 的同事务路径。对照已有 AIP issuer 的私有 passfile 和精确身份预检，但不复用其角色或秘密。
2. 在 `tests/asset_registry` 或现有 `test_ecommerce_growth_cutover_pg.py` 用 signed disposable PG 写 RED：通用 runtime 连接不得完成 active 终结；没有正式安装命令身份必须 fail closed；正确专用登录必须可在同一连接完成终态和 CommandReceipt，异租户、无 Binding、重复键仍拒绝。先检验 MEMBER=true/USAGE=false/SET=false 以及专用 EXECUTE/表 ACL；`aos_app` 当前自身是超管，不可直接登录为正式命令。
3. 若 schema 不能提供窄权限，停止正式接线改动，形成唯一136迁移合同，与 Capability/安装锁并行候选统筹；独立推进可信 evaluator 同最终事务的可验证证明。不得用 superuser、owner、test-only 用户、`SET ROLE aos_app` 或给 aos_runtime EXECUTE 伪造正向。

## 完成与回滚

- 本波至少交付可复现的角色/连接 RED 和最小安全方案；只有 app 身份、租户及同事务 Receipt 均成立才写生产接线。缺正式身份则当前实例继续禁入，纯内容既有路径不得回归。
- 代码变化仅限精确连接入口及相邻测试；新 migration 与当前卷切换另波，需独立可校验备份、全恢复和零执行窗口。复核签名预检、专项/相邻、浏览器失败关闭；精确提交并同步 01/06、D-wave、Prime。
