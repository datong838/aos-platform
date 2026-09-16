# SC4-5L6Y5F4 T 验证：Runtime Host 业务 worker 可观测性

## 结果

- 独立 Host 状态现在持续公开同进程 live target 和 ProductEvent 最近 tick 安全计数，不含业务载荷、凭据或异常文本。
- 当前真实 Host PID 5833 为 active，但 `liveTargets=[]`；ProductEvent 为 targetsChecked/candidates/occurrences/analysesAccepted/failed 全 0。
- 这证明 S 波次 0 occurrence 不是 worker 处理 candidate 失败，而是 worker 没有 process-owned target。

## 根因

- `PostgresPendingPreparationDirectory` 只枚举 `runtime-reconciler` 未投递的 `runtime-apply` outbox。
- `PreparationConsumer` 只在领取该 pending delivery 时创建 PreparedJob 并登记 LivePreparedJobDirectory。
- L generation 已 ready 且原 outbox 已送达；进程重启清空内存目录后，没有 durable ready-generation 恢复路径。仅重启不会恢复业务 worker。

## 验证与边界

- ProductEvent worker 与独立 Host 定向测试 26 passed；diff check 在提交前执行。
- schedule 保持 disabled，未调用 tick、未新增 run、occurrence 或业务写入。
- 下一波必须以当前 ready binding、安装 Receipt、资源 lease、签名包和租户身份重新鉴权并重开运行会话，不能制造 pending outbox 或绕过单写者/Receipt。
