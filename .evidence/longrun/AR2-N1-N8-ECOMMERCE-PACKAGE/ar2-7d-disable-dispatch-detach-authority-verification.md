# AR2-7D D6A1 停用与 dispatch 解绑权威验证

日期：2026-09-10
基线：`m1@ad1d47b1`
结论：`AR2_7D_DISABLE_DISPATCH_DETACH_AUTHORITY_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D6 和 D6 施工方案为权威；m1 单人串行、先方案后编码、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- 本切片只交付 D6A1 authority/readback 原语，尚未把 dependent 注入通用 disable executor；自动联动归 D6A2，不提前声称 D6 或 AR2-7D 完成。
- runtime disable 第一事务完成既有 binding fence 后，只有 exact resumed ecommerce-growth activation 才能创建 subordinate lifecycle operation；固定函数同时锁定 runtime、activation、binding、gate 和 9/9 dispatch，把 gate 暂停并把九项整组 fence。
- runtime disable 成功后，第二个固定函数再次验证 exact disable、binding revision/epoch、暂停 gate、fenced snapshot 与 drain 状态；然后按 activation prepare 保存的 legacy snapshot 恢复九项并删除 gate。
- `fenced` 与 `detached` 状态受 deferred Receipt guard 约束；直接调用数据库函数但不写 Receipt 时，事务提交失败并完整回滚。Receipt/Event 回读校验 canonical hash、租户、runtime/activation identity、phase、operationIds 与 request hash。
- UNKNOWN attempt 只进入 fence/detach Receipt 供后续 reconcile，不被当成 drained 失败，也不被删除或重放；claimed/running 仍由固定函数拒绝。

## 文件与方案一致性

- `services/aos-api/alembic/versions/ar2_017_ecommerce_growth_disable_detach.py`：新增 lifecycle operation/event/receipt、租户 RLS、runtime 对 activation 的只读策略、两个非特权 SECURITY DEFINER 固定函数、Receipt 提交守卫和非空降级拒绝。
- `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`：新增事务内 `EcommerceGrowthDisableDependent`，分别承接 runtime fenced 与 runtime disabled 两个边界；无 resumed activation 时返回 no-op，不自行提交。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：接续 `ar2_017`，覆盖成功、replay、直接函数缺 Receipt、Receipt 篡改、UNKNOWN 保留、无 resumed activation no-op、空/非空 downgrade，并复跑 D5 全部行为。
- 实现符合 D6A1 方案：没有复制安装生命周期，没有改通用 disable wiring，没有调用 handler、Provider 或真实源；D6A2 将复用此 concrete dependent，而不是新增第二套状态机。

## 验证证据

- 完整 ecommerce cutover PostgreSQL 文件：`51 passed, 7 warnings in 14.09s`。
- disable/lifecycle/production 邻接：`97 passed, 7 warnings in 9.77s`。
- Alembic 单一 head：`ar2_017`；专项夹具在每例临时 schema 中按 `ar2_013 → ar2_017` 实际升级，并验证空降级和非空拒绝。
- Closure：`1709 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile 与 `git diff --check`：通过。
- 18434 的 `aos_test_admin` 是专用管理库而非完整应用基线；直接全链 upgrade 在历史 `228ti1e1expand` 缺少 `meta_workspace` 时失败并事务回滚。复核 `alembic_version`、`meta_workspace`、`extension_dispatch_lifecycle_operation` 均无残留，因此不把该次运行计为迁移验证。

## 关键反例与保留边界

- Receipt authority 被受控篡改后，replay 因 content hash 不一致拒绝。
- 没有 resumed activation 的普通 runtime binding 完成 fence 后，dependent 返回 `None` 且不创建 lifecycle 行，原有 disable 合同不变。
- maintainer/runtime 直接调用 detach 函数但缺 detach Receipt，在 deferred 提交点回滚；九项仍为 fenced extension，gate 仍暂停。
- lifecycle authority 为空时可降级 `ar2_017`；存在已围栏 lifecycle operation 时拒绝降级。
- 未执行真实租户停用、真实 dispatch、共享/生产迁移、真实源读取、Provider、费用、发布或 push。D6A2 wiring、D6B 资源释放、D6C 重装隔离、D6D OCI 联合验收仍待施工。

## 内容摘要

- `ar2_017_ecommerce_growth_disable_detach.py` SHA-256：`c6fe4c3a00d3f0f8adf1217b8fb9a977e717d106ceee6302dd1e2553cbfafbfc`
- `ecommerce_growth_lifecycle.py` SHA-256：`f998a4b30431d52037f636cf63f703a7ebbf232ab1bdde3bd850a63362acad47`
- `test_ecommerce_growth_cutover_pg.py` SHA-256：`677321e5cb03ced368bf86f74a07cdf175bd44092841cec0b1452331d0b7abe1`
