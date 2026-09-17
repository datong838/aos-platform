# SC4-5L6Z S 十二源快照关闭、重试与租约禁入验证

时间：2026-09-17  
租户：`org-org/dev-project`  
结论：`S_SNAPSHOT_UNACCEPTED_CLOSURE_AND_RUNTIME_FENCE_GREEN`

## 已完成

- a0v_083 以受限 maintainer 函数关闭 group
  `f8d6b5af-f7a3-5f15-88ee-6432012f9537`，Receipt id
  `11f34b69-2a90-4ef0-93ec-10574d302081`，content hash
  `sha256:9f55f99cc9dbd7dda7f8dc6e513ce77d37c86c57fd217d50bc327c9eeb568444`。
- 关闭事务再次证明 group claim、source claim、ingress command/derived/dataset、snapshot input/member
  均为 0；12 个 run 以固定错误码 `SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM` 终结，
  `businessAccepted=false`。
- P02 只续签新的 selection/control/binding；definition rev8 绑定十二个 current control 后启用。
- dispatch 查询排除具有正式 unaccepted-group closure Receipt 的历史 group；无 Receipt 的未完成组仍阻塞。
- 独立 worker 自然 tick 安全记录 `PermissionError / run_guarded`，外部结果继续为
  `SNAPSHOT_EXECUTION_UNCONFIRMED`，日志不含异常消息、SQL、源数据或凭据。

## 真实运行权威

S installation `77b8e5c2-db96-4d55-a808-1b62e00163d2`、generation
`e621100a-baea-440f-9075-ae8a5290845a` 的三项租约在
`2026-09-17T00:30:35.436590Z` 到期后均被正式恢复器记录为
`cleanup_state=released / observed_release=true`。当前 binding 为：

- `observed_state=unknown`
- `enabled=false`
- `operation_fence=true`
- `execution_epoch=4`
- 唯一 Runtime Host 的 `liveTargets=[]`

因此 worker 的 admission 拒绝符合 fail-closed 合同。rev8 未产生新 group、source claim 或 ingress；
随后通过原 SnapshotScheduleService exact predecessor transition 写入 rev9 disabled，hash
`sha256:946a333b5e73863e689b2e41b6c1f3ccd3eff66cd089ccf6290fca931777bff3`，停止无效 tick。

## 验证

- migration 由 a0v_082 单步推进至 a0v_083，迁移前后既有业务表计数一致，新 Receipt 表初始为空。
- closure、十二源控制、dispatch、worker 生命周期、经营参谋 Policy/Discovery 专项：
  `72 passed / 43.50s`。
- 另一次 dispatch/worker 集成回归：`13 passed / 43.89s`；安全来源分类定向回归：
  `6 passed / 8.48s`。
- `dev-org/dev-project` canary 写入为 0。

## 边界与下一波

本结果证明关闭、重试路由和租约失效禁入正确，不代表十二源 snapshot 已完成，也不代表经营参谋
首链已绿。released generation 不得原地复活。下一波从当前不可变权威建立 clean successor，完成
prepare/verify/configure/enable、九路 successor cutover、唯一 Host live target 和十二源新代控制后，
再恢复自然 snapshot group；禁止手工改 binding、手工插入 snapshot 或直接调用 worker 执行函数。
