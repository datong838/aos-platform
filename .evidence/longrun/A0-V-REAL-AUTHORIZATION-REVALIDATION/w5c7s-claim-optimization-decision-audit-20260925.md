# W5c7s Claim 优化综合裁决（只读）

## 三路径边界

| 路径 | 原读回与异常 | W5c7l–r 证据范围 | 未证/不可外推 |
| --- | --- | --- | --- |
| 原始 running | callback 前后各 `_load`；每次 GroupClaim current 后逐成员 `_bound_parent`，受控 parent 再验 current claim 与 running Run/Schedule/Graph/Source；输入变动报 `GROUP_INPUT_CHANGED_DURING_CONSUMPTION` | 两次 `_load`/拒绝、ClaimLoop 身份/历史不可变、Schedule/Run/Installation 锁、后置时间窗调用 | 同一 `_load` 内若跳过第二次 Owner 读，所有控制/配置/预算/发布派生依赖、锁序、RLS 快照与原错误先后顺序未证 |
| 原始 completed | `_load(completed_read=True)` 走 GroupClaim/ControlledIngress 的 completed current；要求 succeeded、executor stopped、完成时间、derived/dataset receipt 与零 pending；running 写路径必须拒绝 | 原 completed 8 项 PG 通过，含未完成成员、缺/坏 receipt 与当前发布变动 | running 的锁/claim 快照不能代替 completed 的只读完成守卫；不能让成功状态重开 source call |
| saved recovery | `_run_recovery` 用固定 recovery Authority/facts，callback 前后 `read_saved_current` 或 `read_completed_current`，变动报 `GROUP_RECOVERY_INPUT_CHANGED_DURING_CONSUMPTION`；不调用原始 `_bound_parent` | 当前持久会员权限/时间窗与异步拒绝 2 项、disabled/actor/stale ref/failed-unknown/负租户不达 Store 5 项通过 | 原始 `_bound_parent` 优化不应跨入 recovery；任何新 source call、继承旧控制或跨代次缓存均不授权 |

W5c7n 旧 12-source ACK-loss 长例在 900 秒单调预算内正式 1 passed/794.823 秒，性能热点虽在 claim 权威读，但不再构成当前测试准入阻断。W5c7s 没有完整证明同一 `_load` 复用的全部安全/错误等价；风险大于当前收益。**裁决：延期生产查询/claim 复用优化，保留原双 `_load`、逐成员受控重验及三个路径原异常语义。** W5c7o–r 的测试/审计留作未来受控优化前提，不把它们写成已优化。

真实 A0-V closure 仍缺全机 Host universe、Fresh Owner 和独立 closure 方案/key；12 原 Run running、stalled Receipt 0、自动动作 false。下一波回归 Host topology 主线，不以测试 GREEN 推出真实完成或手工重发。
