# 当前已安装 package 一次调用门禁验证

日期：2026-09-12

基线：`631dd962`

结论：`CurrentInstalledPackageInvoker` 已把一次 live package IPC 夹在两笔独立当前性读取之间；
响应只有在 active Installation、lock、binding、epoch/revision、package 与 markings 快照完全未变时返回。

## 验证

- 正向证明第一次连接已关闭后才进入 IPC，IPC 完成后才打开第二次连接，调用次数恰为一。
- 调用中 binding revision 漂移会丢弃响应并拒绝；enabled=false、fence=true、observed 非 ready、
  installation revision 或 lock hash 错误均在 IPC 前拒绝。
- 缺 marking、package 重复、live job 缺失均不调用。
- TimeoutError 与 CancelledError 原样上抛，一次调用、无第二次读取、无重试。
- 定向测试 `11 passed`；`git diff --check` 通过。
- 累计 invoker/directory/owner/consumer/coordinator/service 回归：`48 passed, 14 skipped`。
- AR2-7 closure：扫描 1781、分类 147、迁移 93；全部错误数组为空。
- 本波不写数据库，不修改 Installation/Registry/package/租户业务数据。

## SHA256

- invoker：`d868b18c1c4f4c726b1986f377172fb8f74bac30de487122858aecc8c3d740c4`
- tests：`47df876705c6eb55732b86e8b6b218bed6555671973ab2682ecbdc7b6db03d60`
- plan：`1d30c4203241fa992f30f89be3aba558f9209aaf91a32d17956163bc6e12615b`

## 下一门

增加 stage-review composition factory，把同一固定 invoker 注入
`AsyncAnalystStageReviewCommandService`；同时把 invoker 的 exact runtime snapshot 纳入 stage review
prepared/current commit 封印，避免第五次 IPC 后到 StageDecision 发布前的运行代际漂移。
