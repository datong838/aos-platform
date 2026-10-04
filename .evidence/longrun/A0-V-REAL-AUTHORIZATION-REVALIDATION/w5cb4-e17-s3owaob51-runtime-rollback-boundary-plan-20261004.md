# b51｜运行安装旧 rollback 不能绕停用/卸载（文件级计划）

基线 `m1@d9419e7d`、AOS-001309，当前真库135只读。复习 231-3 §1/§3：运行安装旧入口不得绕 RuntimeOperation，且“**不使用 rollback 假冒卸载**”；BIND-1 不把目录/页面状态当可运行事实。

## 定位

- 生产 `build_installation_service` 已注入 `RuntimeUninstallGuard`，但 `InstallationService._append_rollback` 只查 replacement，随后原 Store 允许 active→rolled_back；它未调用任何 runtime 守卫。`uninstall` 才调用 `before_uninstall`。原 `bundle_installations` router 暴露 rollback，故这是运行安装的独立绕路。
- 不把原合法 content rollback 一并关闭；复用既有 `legacy_content_predicate` 从 exact StoredCompositionLock 的当前 resolved 成员及 Registry hash/manifest 判断是否纯内容。false/缺失/损坏均失败关闭。guard 只读，不执行资源回收或 RuntimeOperation；仍须同事务安装头已锁与 CAS。

## 精确施工/验证

1. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：独立 `AOS_B51_RUNTIME_ROLLBACK=1` 完整 signed Growth1.13 disposable PG/OCI 模式，以**生产相同 RuntimeUninstallGuard** 的 InstallationService 对 active runtime 走原 `rollback`，先 RED；期望 `RUNTIME_OPERATION_REQUIRED` 409、原安装 active/ETag、无该 key Receipt。保留默认路径和 OCI cleanup。
2. `services/aos-api/aos_api/extension_runtime/runtime_uninstall.py`：仅增只读 `before_rollback(conn, lock)`，要求当前事务、纯内容 predicate 精确 true，否则 `RuntimeOperationRequiredError`。`services/aos-api/aos_api/asset_registry/installation_service.py`：仅在已配置 runtime guard 的 `_append_rollback`、原 replacement 检查后调用它；无 guard 的隔离/旧纯内容构造合同不变。
3. 目标与相邻：新增 test-only 模式、既有完整 signed 默认/撤销竞态模式、RuntimeUninstallGuard 单测、content rollback 既有专项、API 错误映射、相邻回归、语法与 diff check。复审 guard 查询只读、租户/lock hash来自已锁当前安装、403/409不泄露来源，回滚失败无 Receipt/指针副作用。

本波不实施 active 安装换代正向竞态，不把旧 rollback 当合法生产者。后续真正 runtime uninstall/reinstall 须原 RuntimeOperation、审批/排空/资源义务齐备；当前实例缺 authority 继续禁入，Host/worker/Provider关，不改真库/迁移、不读商城源/旧Run/230 L0、不 push。
