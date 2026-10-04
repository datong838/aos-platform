# b57 文件级方案｜签名安装命令 Receipt 与终态同事务

## 已读事实

- 231-3 要求运行安装卸载先停用、排空、确认资源释放，再在原 Installation 不可变历史与 Runtime terminal Receipt 同事务提交。b56 仅在真实 `ar2_018` 隔离迁移夹具验证专用低权登录能终结 terminal Receipt；`bundle_installation_command`/完整 signed Growth1.13 链未纳入该夹具。
- `test_growth_signed_installation_full_schema_pg.py` 已用本地签名 Growth1.13、全迁移隔离 DB/OCI 达到 active；其 b52 分支将 Binding 删除作为故障负例，断言旧 uninstall CommandReceipt=0。该分支的 test-only `GRANT EXECUTE TO aos_runtime` 只是隔离探针，不可复制到正式正向。
- `test_ecommerce_growth_cutover_pg.py` 可合法 disable/detach/release 后得 terminal Receipt，但资产表仅为精简真实字段。`PostgresInstallationStore.execute_idempotent` 在同连接中绑定租户、取幂等锁、运行 handler 并写 `bundle_installation_command`；完整正向必须连接两个现有夹具的事实，不能靠手工 Run 或直接写当前库。
- 文件级复查后，full signed fixture 只做 active 与 b52 缺 Binding 故障注入，没有合法 disable/detach/release 生产者；cutover fixture 的 `_complete_runtime_disable` 含隔离直接状态推进，不可移植为正式资源生产者。因此本波先执行下述原 Store/终态同事务合同子证明，并清楚保留 signed 全链待办。

## 文件级动作

1. 先审 `test_growth_signed_installation_full_schema_pg.py` 的 active 后合法 disable/detach/release 生产者是否齐备，找可复用脚本/夹具；只在 disposable signed 库做。新增 b57 mode 的 RED 先要求专用低权角色无法继承/SET app、runtime 直调仍拒绝，且同连接执行原 `InstallationService.uninstall` 后，terminal Receipt、安装修订、CommandReceipt 一起提交。
2. 因 full signed 夹具暂无合法 disable/detach/release 生产者，先在精简真实迁移夹具建立源自 `228asset1` 的 CommandReceipt 必要列、RLS/主键（并非全量迁移表约束），调用原 `PostgresInstallationStore.execute_idempotent`，将 `RuntimeUninstallGuard`、安装修订与 CommandReceipt 放同一连接事务。覆盖强制回滚、重复键、错租户及 runtime/直接 DML 负门；明确这是合同子证明，不冒充 signed 全链。
3. 验证异租户、旧 ETag、重复键、异常回滚不留半写；专项与相邻回归、浏览器失败关闭、代码/231-3 一致性审查。正式专用凭证/连接装配及唯一136切换另波，须独立备份、全恢复、零执行窗口。

## 改动边界

- 目标仅测试与必要的最小生产接口；先有 RED 再改代码。当前权威卷只读，Host/worker/Provider关闭；不读商城源、不重放旧12Run、不手工 run_definition、不碰230 L0、不 push。
