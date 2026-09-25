# W5c9b｜原十二 Run 与 authority 只读对账审计

方案 `m1@7edaed1f`。真实 Docker 仍只有 `aos-a0v-recovery-pg` Up；18181 纯 HTTP PID26881 存活并只监听 loopback，8080 无监听/job。没有启动自然 worker 或查询商城源行。使用既有 W5c4t `observe()`：所有 SQL 在 `SET TRANSACTION READ ONLY` 事务中，限定已提交的精确 DEFINITION/GROUP/GENERATION；只输出聚合与状态，不输出请求 payload/凭据。

2026-09-26 03:49 CST 左右读回：定义 head rev4 disabled、原 claim 1、原 attempt 精确 ID `a5e60b0d-2d97-44d0-88bf-9f08990624d1`，state=failed、reason=`RECOVERABLE_EXECUTION_EXCEPTION`、errorType=`PermissionError`。原组 Run 12，`stalled=12`，最后 started=`2026-09-24T20:00:04.800482Z`。effects：group claim/input 各 1、member 12、source claim 12、ingress command 12、derived command 0、dataset receipt 0。全租户 Store Receipt 总数 26（**不是本原组已完成 Receipt**），live link 0、projection pending 0、canary 0，原组 stalled/unaccepted closure Receipt 均 0。分类 `STALLED_WAIT_24H`，`automaticAction=false`；严格最早时间为 `2026-09-25T20:00:04.800482Z` 之后，届时仍不授权关闭。

复核既有 W5c5g 组合门时，`knownHost.observe()` 因重启后历史 Host 进程基线不匹配抛 `ValueError`；未绕过重试为 GREEN。其它只读子观察器正常：独立 closure audit=`NOT_YET_CLOSED`、runningRuns=12、closureReceipts=0；managed directory=`...INCOMPLETE_TOPOLOGY`、runningOriginalRuns=12、releasedResourceLeases=3、closureAuthorized=false。跨面的全机 Host 拓扑、单事务 Owner 门和正式退休/direct successor 仍缺，时间到线不授权真实 closure。
