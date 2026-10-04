# b57｜低权终态与原安装 CommandReceipt 事务子证明

## 方案复审和夹具限制

- full signed Growth1.13 `test_growth_signed_installation_full_schema_pg.py` 到 active 后没有正式合法 disable/detach/release 生产者；b52 分支只删除 Binding 做故障负例，曾临时向 runtime 授函数 EXECUTE，不能挪作正向证明。cutover PG 夹具有合法终态但 `_complete_runtime_disable` 含隔离直接状态推进，不能宣称完整正式业务生产者。
- 因此本波按方案 fallback：在已有 `ar2_018` 真实迁移隔离 schema 中，仅增加 `228asset1` 命令表的必要列、主键和强制 RLS，调用**原** `PostgresInstallationStore.execute_idempotent`、`RuntimeUninstallGuard` 和安装修订写入；此表不是全量迁移定义。只证明连接与提交原子性，不证明 full signed/正式卸载。

## RED/验证

- b56 已有无授权拒绝、低权不可 SET/继承 app、不可直接改 Binding、错租户拒绝；本波在同一新测试加入强制 `RuntimeError`：guard 先写 terminal Receipt/Binding 后异常退出，事务回滚，terminal Receipt=0、CommandReceipt=0。之后正常命令在同一连接执行，终态 Receipt=1、CommandReceipt=1，返回 `replayed=false`；同键再次调用提供“若执行则失败”的 handler，返回 `replayed=true`，不重发。
- 命令 `AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_PG_PORT=18434 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py -k 'dedicated_noninheriting_installation_command_role or runtime_uninstall_guard_commits_exact_terminal_authority or runtime_role_cannot_call_application_uninstall_command or runtime_uninstall_guard_requires_same_transaction_installation_revision or runtime_uninstall_guard_rejects_unreleased_resource' --tb=short --disable-warnings --maxfail=1`：exit0，`5 passed, 64 deselected, 7 warnings`。
- test-only 动态角色残留数0，`git diff --check` exit0。无生产代码/迁移修改，当前真实库135只读，Host/worker/Provider关。

## 尚未证明

- 正式 signed Growth 1.13 active→合法 disable/detach/release→低权 `InstallationService.uninstall` 全链；真实 `bundle_installation_command` 全约束/真实资产 Store revalidator；正式凭证/连接装配与当前卷迁移。下一波先补正式资源生产者或在完整 signed 克隆证明其缺口，不能使用旧 Run/手工 `run_definition`、超管/owner 或 test-only 授权捷径。首链仍 pending。
