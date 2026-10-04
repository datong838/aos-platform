# b56｜专用低权安装命令角色隔离验证

## RED 与最小测试改动

- 只改 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`，复用真实 `ar2_018` 等迁移的无卷 PG fixture，不改生产代码/迁移/当前库。动态专用 LOGIN 设 NOINHERIT/NOSUPERUSER/NOBYPASSRLS，app 成员 `INHERIT FALSE, SET FALSE`。当前库预览 `aos_app` 是超管，不能直接当正式命令身份。
- 首轮新专项 exit1：无 schema USAGE 时 `UndefinedTable`，说明未显式授权即失败关闭；按 PG 实际错误收紧预期。第二轮 exit1：授资产表和函数权限后，guard 仍因缺 `extension_runtime_uninstall_receipt SELECT` 被拒；补精确 SELECT。该轮清理时因测试角色尚有对象 ACL，`DROP ROLE` 失败；手动只在 test-only 库删除遗留随机角色，并在测试 `finally` 加 `DROP OWNED BY` 清除测试授权，复核没有遗留角色。
- 再加 `bundle_installation` 列级 UPDATE（仅 current_revision/etag_version/active_revision），无需整表 UPDATE；新增专用角色对 `extension_runtime_binding` 直接 UPDATE 被拒，以及 `dev-org` GUC 下请求 org-org 终态得到 `SerializationFailure: current active installation authority is required`。错租户预期按实际 DB 失败码校正，无数据写入。

## GREEN 与边界

- `AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_PG_PORT=18434 ...pytest -q test_ecommerce_growth_cutover_pg.py -k 'dedicated_noninheriting_installation_command_role or runtime_uninstall_guard_commits_exact_terminal_authority or runtime_role_cannot_call_application_uninstall_command or runtime_uninstall_guard_requires_same_transaction_installation_revision or runtime_uninstall_guard_rejects_unreleased_resource' --tb=short --disable-warnings --maxfail=1`：exit0，`5 passed, 64 deselected, 7 warnings`。真实卸载函数、Binding/terminal Receipt 和 constraint 在同一事务；原 app-role 正向、runtime 负向、未排空和缺同事务修订负门未回归。
- test-only 容器查询 `SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ar2_install_command_%'`：exit0，0；`git diff --check` exit0。`DROP OWNED BY` 只清本次动态角色在 test-only schema 的 ACL；未删除数据库、卷、备份。
- 此试验证明低权登录在明确 GRANT 下可终结 runtime 及终态 Receipt，且不能 SET/继承 app 角色或直接改 Binding。尚未证明原 Installation CommandReceipt 同事务、完整正式权限策略、凭证来源、API 连接装配或真实库迁移；当前实例继续禁入。下一波 b57 用真实资产命令 schema/Store 与 signed 资源链验证完整事务和重复/租户负门，再审正式迁移与连接入口。
