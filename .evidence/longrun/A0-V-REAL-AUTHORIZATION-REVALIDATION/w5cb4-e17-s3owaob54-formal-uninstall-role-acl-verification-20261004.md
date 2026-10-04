# b54｜正式卸载角色边界与 b52 兼容修正

## RED/修正证据

- 既有 `test_ecommerce_growth_cutover_pg.py` 含 `aos_app` 同事务卸载 Receipt 正向、`aos_runtime` 直接调终结函数负向及未附同事务安装修订的约束负向。最初复跑 exit1：18434 listener 未启动。只在 `colima-aos-a0v-test-only` 启动无数据卷的 `aos-b54-acl-pg`（`postgres:16-alpine`，127.0.0.1:18434）；第一次 PG 重跑 exit1，缺 test-only `aos_extension_maintainer`/`aos_app` 角色；在该隔离容器创建两 NOLOGIN/NOBYPASSRLS 角色后重跑。
- 角色齐备后既有三项为 `2 failed/1 passed`：b52 改动提前要求 `StoredCompositionLock`，让原 app-role 已经有 Binding 的合法 guard 正向和同事务约束测试均在函数前被拒。这是 b52 的真实兼容回归，非测试环境伪失败。
- 最小生产修正只改 `runtime_uninstall.py`：显式安装锁存在时先用既有 `legacy_content_predicate` 保持纯内容旧合同；运行锁调用原 SECURITY DEFINER 函数，只有其空三元组才对已提供锁的上层安装命令拒绝409；原直接 guard 调用无锁但有正式 Binding/Receipt 继续原行为。非法非锁对象仍拒绝。没有给 runtime 角色授终结函数 EXECUTE。
- 重跑原三项 exit0 `3 passed/65 deselected/7 warnings`；b52 完整 signed Growth1.13 缺 Binding 故障注入 exit0 `1 passed/7 warnings`；纯内容 rollback/uninstall 与 approved guard 共 `7 passed/7 warnings`；`compileall -q`/`git diff --check` exit0。先前 b52 的相邻32 passed/2 xfailed 已保留，因本次只移动守卫分支，未重跑相同集合。

## 权限结论与风险

- 原三项证明应用角色在合法 detach+释放后可同事务终结，运行角色直接调用被拒；因此给 `aos_runtime` 全局 GRANT EXECUTE 会破坏既有刻意负门。正式生产应将资产安装控制命令的**受信应用身份**与 runtime worker 身份拆开，并确保当前租户/签名锁/Receipt 在同一连接事务内；不能靠当前特权预览 API 或 HTTP roles 冒充。
- 当前代码 `build_installation_service` 默认 `PostgresInstallationStore(connect)`，`apply_asset_transaction_scope` 在 TI6 已装时切 `aos_runtime`，故生产合法 active 卸载仍不能宣称可用。正式 app 身份的接线和唯一136/当前卷切换仍待独立波；当前权威库135只读、Host/worker/Provider关、首链 pending。隔离容器未删除，避免误删历史库/容器。
