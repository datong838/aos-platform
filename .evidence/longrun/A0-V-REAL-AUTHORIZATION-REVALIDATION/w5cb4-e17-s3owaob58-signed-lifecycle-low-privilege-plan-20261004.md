# b58 文件级方案｜现有 signed 全链的专用低权身份

## 复习与纠偏

- 231-3 要求 signed runtime active 后正式 disable→Host/Owner 排空→dispatch detach→真实 OCI 资源释放→原 InstallationService 同事务卸载/Receipt→新安装代次重装。b56/b57 已有隔离低权角色与两 Receipt 原子性子证明，未宣称正式实例正向。
- b57 只检查 `test_growth_signed_installation_full_schema_pg.py`，其到 active 后未实现合法停用。b58 文件检索发现另一个既有 `test_ecommerce_growth_signed_lifecycle_pg.py::test_signed_disable_uninstall_reinstall_routes_exact_ecommerce_group` 已按上述路径完整执行；b57 文档“full signed 夹具缺生产者”应限定为前一文件，不能泛指全项目。下一次上下文更新必须纠偏。
- 现有 signed lifecycle fixture 通过一个随机低权 session_user 同时授 aos_app/aos_runtime/aos_extension_maintainer 成员，`_app_connect` 再 `SET ROLE aos_app`。这验证业务流程但不满足 b56 的专用命令登录无继承/不可切换边界；当前真实预览 `aos_app` 还是超管，不能直接用于正式命令。

## 文件级动作

1. 只读定位 `_app_connect`、fixture 角色/GRANT、signed 两代次合法 disable/release/uninstall/reinstall 的精确测试路径及运行时环境；选在该测试中新增专用 app 命令登录（NOINHERIT/NOSUPERUSER/NOBYPASSRLS；`GRANT aos_app ... WITH INHERIT FALSE, SET FALSE`），不修改既有 runtime worker 身份。
2. RED 先把 `guarded = InstallationService(store=PostgresInstallationStore(_app_connect...))` 替换为专用低权连接，要求不 SET ROLE app；观察最先缺的函数/表 ACL。随后仅在 disposable schema 显式加必需 GRANT，直至现有 signed 全链原样 GREEN；反证专用登录不能 SET/继承 app、不能直接改 runtime Binding。
3. 同事务回读原 Installation CommandReceipt、runtime terminal Receipt、修订和重装代次；保留现有错租户/旧代次负门与 OCI 容器数量回零。专项及相邻回归；若原 fixture 依赖高权 GRANT 无法安全收窄，保留 RED 与精确依赖，不在当前库迁移/授权。

## 边界

- 当前 `aos_current_preview_20260927@a0v_135` 只读；仅无卷 PG/隔离 OCI。Host/worker/Provider 正式实例继续关闭，不读商城源、不回放旧 Run、不手工 run_definition、不碰230 L0、不 push。正式身份/唯一136/当前卷切换另波需备份、全恢复与零执行窗口。
