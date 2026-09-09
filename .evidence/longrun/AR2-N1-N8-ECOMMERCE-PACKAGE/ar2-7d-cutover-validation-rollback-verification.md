# AR2-7D D5C2 验证窗口失败回滚权威验证

日期：2026-09-10
基线：`m1@3d6641a4`
结论：`AR2_7D_VALIDATION_WINDOW_ROLLBACK_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D5 和 D5C 施工方案为权威；m1 单人串行、先方案后编码、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- rollback 只接受 activation 仍为 `committed` 或 `validated` 的验证窗口。`resumed` 后拒绝使用该捷径，后续生命周期回退归 D6。
- `prepare_validation_rollback` 要求新的 exact `ecommerce_growth_cutover_rollback` ActionApprovalEvent，绑定 activation operation、commit Receipt、group revision、九项 operationId 和目标 runtime identity；当前审批在 fence 与最终 rollback 前都重新锁定、重验。
- fence 函数在同一事务核对 target runtime disabled/fenced、paused gate 和 9/9 exact extension snapshot，再把九项整组推进为 fenced extension snapshot并把 gate Owner 转给 rollback operation。任一权威漂移整事务失败关闭。
- `commit_validation_rollback` 再次枚举 occurrence、dispatch attempt 和 runtime attempt；claimed/running 阻断，UNKNOWN 只写入 Receipt 供 reconcile。排空后，固定函数把九项整组 CAS 回 activation prepare 的 legacy identity，删除 rollback gate；target runtime 继续 disabled/fenced，不调用 handler。
- rollback 的 `draining` 与 `rolled_back` 状态受 deferred Receipt history guard 约束。maintainer 直接调用最终函数但不补 drain/rollback Receipt 时，提交失败，dispatch、gate 和 operation 全部回滚到 fenced/draining。

## 文件与方案一致性

- `services/aos-api/alembic/versions/ar2_016_ecommerce_growth_cutover_rollback.py`：新增 rollback parent/commit/failure 权威、fence 与 rollback 两个 SECURITY DEFINER 固定函数、rollback 状态 Receipt 门及非空降级拒绝。
- `services/aos-api/aos_api/ecommerce_growth_cutover.py`：新增严格 rollback 请求/Receipt、独立审批 payload、fence/commit 方法、三阶段不可变 history 与 readback；不导入领域 bundle。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：接续 `ar2_016`，覆盖 9/9 回滚、窗口关闭、审批/Receipt/dispatch/runtime/gate 漂移、运行中任务、UNKNOWN、角色权限、直接函数与 downgrade。
- 实现与方案一致：成功路径恢复 legacy dispatch，保留 runtime fence；失败路径保持 rollback fence；没有新增真实调用、自动重放或跨租户入口。

## 验证证据

- D5 cutover PostgreSQL 专项：`44 passed, 7 warnings in 12.20s`。
- Router/Host/occurrence 邻接：`39 passed, 7 warnings in 3.16s`。
- 完整 `tests/extension_runtime` 串行复跑：`1228 passed, 28 skipped, 7 warnings in 84.03s`。
- Alembic 单一 head：`ar2_016`。
- Closure：`1708 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile、局部 lint（若环境提供）与 `git diff --check`：通过。

## 关键反例与运行轨迹

- 单条 dispatch revision、runtime revision、gate revision 或 rollback Approval 任一漂移，fence 前拒绝且不创建 rollback operation。
- rollback Approval 在 fence 后失效，最终 rollback 再次拒绝；恢复 exact 当前审批后才允许继续。
- 受控注入的异常 running runtime attempt 阻断 rollback；转为终态后同一 rollback operation 才能完成。
- UNKNOWN dispatch attempt 被写入 rollback Receipt 并保持 `unknown`，没有 handler 重放。
- runtime 角色没有函数执行权；maintainer 直接调用 rollback 函数但缺 Receipt，在 deferred 提交点回滚全部九项与 gate。
- 空 rollback 权威允许 `ar2_016` 降级；存在 rollback operation 时拒绝降级。
- 电脑重启后首次专项迁移发现专用 18434 集群测试角色缺失，恢复隔离角色后专项全绿；首次全量发现历史用例固定使用的 18432 容器未启动，恢复该隔离容器后从头串行全绿。两次均为测试夹具启动前失败，没有业务断言失败。

## 内容摘要与保留边界

- `ecommerce_growth_cutover.py` SHA-256：`1a099cb585c807976e2d7ae3eccfbc07be7b9f23bb0c10b5bd9f724b34d3fc70`
- `ar2_016` SHA-256：`46840480693cd1076b699922cf69997d0bf1a1a5eb738a440296e99ed861c717`
- `test_ecommerce_growth_cutover_pg.py` SHA-256：`a0cb4bb494ea982c58ee6416d067d9fbaf4abc982b887ccafde648c3ecdc5ccb`
- 未执行真实 cutover、真实租户写入、共享/生产迁移、真实源读取、Provider、费用、发布或 push。D6 lifecycle 与 7E/A0-V 仍未封板。
