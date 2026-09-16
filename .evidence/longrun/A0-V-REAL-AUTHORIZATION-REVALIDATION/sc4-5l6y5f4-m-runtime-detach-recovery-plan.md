# Y5f4-M 配置刷新后 Runtime 禁入、Detach 与恢复方案

日期：2026-09-16

基线：m1 `415e2365`

## 目标

在 J 代 event-control 已正式 shrink、旧 epoch unknown 已闭包后，证明九条业务 dispatch 仍可通过正式 runtime disable 生命周期禁入、排空并 detach；随后只从不可变 installation/configuration/refresh 权威恢复到 ready，不启动 schedule、商城源读取或自然经营 Run。

## 固定路径

1. 只接受主库 a0v071、active installation revision 5、runtime revision 9 / epoch 5 / ready / enabled / unfenced、九条业务 dispatch epoch 5 / group revision 33、event-control=0。
2. 最新 ConfigurationRefreshReceipt 必须为 `708dd66a-787c-43b5-be8e-4953e37a24cd@1`，九路状态必须与其 target 和最新 shrink afterSnapshot 一致。
3. RuntimeDisableService 以当前 installation apply 权限、强 ETag 5、binding revision 9 和固定幂等键创建 disable operation；不得直接更新 binding 或 dispatch。
4. RuntimeDisableConsumer 先调用 EcommerceGrowthDisableDependent 原子 fence 九路，并在同一生命周期 Receipt 中保留 configurationRefreshRef；GenerationDrainReader 只在 running=0 时完成 disable。
5. after_runtime_disabled 必须以精确 fence Receipt、零 unknown attempt 和旧 activation 权威 detach 九路，恢复 legacy snapshot；同键 request 和 consumer replay 必须不产生第二次 detach。
6. 恢复阶段先只读重建当前 installation、最后成功 configuration、disable/detach Receipt 与 package release；走正式 configure/enable/registration 路径恢复新 generation/epoch，禁止手工补 dispatch。

## 首次真实执行发现与修订

首次执行已产生且只产生一个成功的 RuntimeDisable operation：`178a52b9-b8db-4b35-9c0a-66288bd703c8`。binding 已由 revision 9 推进至 revision 11、epoch 6、disabled/fenced/unknown，但共享控制面在传入 `registration_connect` 时没有自动装配 `EcommerceGrowthDisableDependent`，因此九路 dispatch 仍停留在刷新目标 epoch 5 / group revision 33，且没有生成 lifecycle operation/Receipt。该状态是已知成功禁用后的缺失回调，不得重发 disable。

修订后的产品与恢复约束：

1. 共享 `build_runtime_control_plane` 在存在 `registration_connect` 且调用方未显式提供 dependent 时，必须自动装配电商禁用 dependent；不带电商注册连接的通用控制面仍保持无领域依赖。
2. 增加专用的 succeeded-disable 恢复入口，不放宽常规 `after_runtime_fenced`。恢复只接受 operation status/phase 均为 succeeded、binding revision 为刷新目标 +2、epoch 已前进、disabled/fenced/unknown、九路仍完整挂在同一 activation/refresh 权威的状态。
3. 恢复前必须再次证明 runtime running=0、occurrence claimed/unknown=0、lifecycle operation/Receipt=0；否则整笔事务失败。
4. 恢复入口在一个租户事务内按原有正式函数生成 fence Receipt、执行 detach、生成 detach Receipt；不得直接 UPDATE dispatch，不得伪造 Receipt。重放必须返回同一 Receipt。
5. 固定执行器只读取既有 operation id 并调用恢复入口；不会再次调用 RuntimeDisableService.request 或消费 outbox。

## 验收

- disable operation succeeded，binding disabled/fenced，九条 extension dispatch 已 detach，event-control 仍为 0。
- fence/detach Receipt 均携带精确 ConfigurationRefreshReceipt 引用；Receipt 内容哈希和 replay 一致。
- running/claimed/unknown=0；canary 零可见，externalEffects=0，businessRunsResumed=0。
- 恢复后 one active ready/unfenced binding、九条 extension dispatch 原子注册、配置 ref 可追溯；schedule 仍禁用。
- 任一权威、Revision、Receipt、排空或租户检查漂移时在写入前停止。

## 文件范围

- `scripts/a0v_j_runtime_disable_detach.py`
- `services/aos-api/aos_api/asset_registry/control_wiring.py`
- `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`
- 对应装配与 PostgreSQL 恢复测试
- 后续固定恢复执行器
- 本计划及对应 JSON/Markdown 证据
