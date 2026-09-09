# AR2-7D D6B1 runtime uninstall 资源清理验证

日期：2026-09-10
基线：`m1@110f509d`
结论：`AR2_7D_RUNTIME_UNINSTALL_RESOURCE_CLEANUP_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D6/C10/J04 和 D6 细化施工卡为权威；m1 单人串行、最小实现、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- 主动卸载清理与过期 preparation recovery 分离：只扫描 exact tenant + installation + generation + engine context 的 ownership lease，并在每个资源锁内重新验证 runtime disabled、D6A lifecycle detached、disable succeeded 及 fence/detach 两份 Receipt。
- 对已创建资源先把 `cleanup_state` 提交为 `uncertain`，再在事务外调用 cleanup-only OCI driver；只有 exact owner/name/container id 的删除返回 true，第二事务才写 `released/observed_release=true`。
- 删除异常、false、进程崩溃或已存在 uncertain checkpoint 都保持 unknown outcome；同一资源再次进入时不再次调用 OCI。已 released 只读幂等返回。
- 本切片不修改 Installation uninstall transition；D6B2 前置门尚未完成，因此不声称完整卸载可用。

## 修改文件

- `services/aos-api/aos_api/extension_runtime/reconciler.py`：新增 exact-generation candidate scan 和 `begin_uninstall_cleanup` checkpoint。
- `services/aos-api/aos_api/extension_runtime/runtime_uninstall.py`：新增单资源锁、两事务、事务外 OCI 删除的固定 executor。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：覆盖成功、unknown one-shot、未 disable/detach 零 OCI 调用。

## 验证证据

- D6B1 专项：`3 passed, 54 deselected, 7 warnings in 3.93s`。
- 完整 ecommerce cutover PostgreSQL：`57 passed, 7 warnings in 16.12s`。
- ResourceJournal/recovery/lifecycle 邻接：`99 passed, 6 skipped, 7 warnings in 12.21s`。
- Alembic 仍为单一 head `ar2_017`，本切片无 schema 变更。
- Closure：`1710 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile 与 `git diff --check`：通过。

## 风险与保留边界

- `uncertain` 不等于释放，后续 D6B2 guard 必须拒绝；需要人工或专门 reconcile 取得新的确定观察，不能用重试删除冒充确认。
- 清理 checkpoint 复用既有 ResourceJournal 事件，会把原 preparation operation 标为 `needs_attention/RESOURCE_CLEANUP_UNCERTAIN`，成功删除后保留这段诚实历史；卸载门以 lease 的最终确定状态判断，不擦除历史。
- 未执行真实 OCI 删除、真实租户卸载、共享/生产迁移、Provider、费用、发布或 push。D6B2/D6C/D6D 仍待施工。

## 内容摘要

- `reconciler.py` SHA-256：`be1a0548afa7ff63cadcfc1b1c9077e011e4b3b8c70a125f4768581a04227e1b`
- `runtime_uninstall.py` SHA-256：`f9253ca7a0ee5ea6d131cc23b98202d0d09297848d2f7b0a99861c57d4af8413`
- `test_ecommerce_growth_cutover_pg.py` SHA-256：`da375da7583e6c961f107af4760d87a94129335baa9c255ad243a78c43744be7`
