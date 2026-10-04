# b58｜signed 两代次合法停用卸载重装与专用低权命令

## 先纠正 b57 的搜索范围

- b57 复查的 `test_growth_signed_installation_full_schema_pg.py` 只到 active；但本波找到另一个既有 `test_ecommerce_growth_signed_lifecycle_pg.py`，其 `RuntimeDisableService`→`RuntimeHost/LiveInstallationLifecycleOwner`→`RuntimeDisableConsumer`→dispatch detach→`job.stop()` 真 OCI 删除/资源 released→原 `InstallationService.uninstall`→第二代安装与 cutover 已有完整隔离流程。b57 “full signed 夹具缺生产者”仅适用于前一个文件，不能泛指全仓。此纠偏已写本波计划，并须同步 01/06/D-wave。
- 该测试用本地真实签名、隔离 PG/OCI，非当前正式 Growth1.13 发布/配置/身份/首链。正式实例仍不得启动 Host。

## RED 与最小修正

- 基线原测试 exit1 `UndefinedTable extension_dispatch_cutover_approval_refresh_receipt`：夹具遗漏已有 `a0v_051/052/053`；补原迁移顺序后 exit1 `UndefinedFunction extension_dispatch_retired_read_lock_a0v_092`，补已有 `a0v_092`；随后 exit1 `permission denied for table asset_bundle`，因 b54 guard 的内容判定需 Registry 两表只读，向隔离 app fixture 补两项 SELECT。原 signed 全链复跑 exit0 `1 passed/7 warnings`。
- 将原 `_app_connect` 的可 SET ROLE 复合登录替换为独立动态专用 LOGIN：NOINHERIT/NOSUPERUSER/NOBYPASSRLS，`aos_app MEMBER=true/USAGE=false/SET=false`、非 runtime 成员。未显式 GRANT 时 RED exit1 `UndefinedTable bundle_installation_command`。仅在隔离 schema 显式授 USAGE、资产安装读/列级 UPDATE、命令/事件/修订 INSERT、Registry 读、终态 Receipt 读、函数 EXECUTE，并对资产表赋双租户强制 RLS policy；`bundle_installation` UPDATE 仅 current_revision/etag_version/updated_at/active_revision。
- 完整重跑 `AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_ecommerce_growth_signed_lifecycle_pg.py --tb=short --disable-warnings --maxfail=1`：exit0，`1 passed/7 warnings`。测试额外断言专用登录不能 SET ROLE aos_app、无 Binding 直接 UPDATE、非超级/非 BYPASSRLS，且首代原 CommandReceipt=1、terminal Receipt=1；既有第二代新安装、cutover 精确旧代拒绝、OCI 容器数回到基线、资源 released 和历史不可变断言仍通过。
- test-only `aos-ar1c-pg` 动态 `ar2_command_%` 角色残留数0，`git diff --check` exit0。浏览器 CUA 当前发布页仍 org-org/dev-project、37仅评测/已发布0、三 blocker、按钮 disabled、无电商工作台入口。

## 实例边界与下一门

- 本波证明本地 signed 两代次的既有合法停用/释放/卸载重装测试在专用低权命令身份下可通过；未提供正式生产凭证、连接工厂、唯一136迁移或当前 Growth1.13 active 安装，也未证明自然经营首链。当前真实库135只读，Host/worker/Provider保持关闭。
- 下一波审**生产连接装配**与最小正式角色/ACL 迁移合同，并与 Capability/安装锁/可信 evaluator 的唯一136排程协调；当前卷切换须新备份、全恢复和零执行窗口。不得拿 test-only 登录或本地签名当正式实例身份。
