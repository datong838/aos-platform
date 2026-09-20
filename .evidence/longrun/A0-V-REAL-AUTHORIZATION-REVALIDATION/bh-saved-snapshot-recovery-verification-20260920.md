# BH 保存快照恢复、1800 秒预算与单 attempt 冻结验证

## 配置与 authority 转移

- definition rev103 disabled、BH attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev103 disabled 生成 BH rev104 disabled，hash
  `sha256:320e30a2db34879aa3f463cdf47cfc248538b9a3de32247424ce48ca9a5e409e`。
- renew 从 recovery rev33 生成 rev34，hash
  `sha256:05af21e617daac50947f16963fb01277d170c3cf4a5c1e493c27a3ea8de676e6`；同一事务生成
  definition rev105 enabled，hash
  `sha256:74ecf1e89f33516c99dc001063c6fa5318d4937d4907d7acd9f720ec87dcdb63`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与单次终态

- 创建 exact `A0V-BH-SNAPSHOT-WORKER-20260920` deployment lease 后，由同一 supervisor 启动唯一自然
  snapshot worker PID 99659；读回 worker=true/topology=independent、Runtime Host=false、Cron=false，未调用
  `run_definition`。
- 唯一自然 attempt `6d8395b6-b04b-4aa3-b002-9b3618e1eaf3` 使用幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision60；
  supervisor 以数据库 `accepted_at` 为起点，在 elapsed=1800 秒命中预算，对 exact worker 进程组仅发送一次
  SIGTERM，并在 180 秒排空预算内确认 return code -15、`workerStopped=true`。
- worker 于 `2026-09-20T02:57:58Z` 完整停止，状态 `STOPPED/taskAlive=false`，18181 无监听；唯一 attempt
  于 revision61 正式收敛为 `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`，
  `completedAt=2026-09-20T02:57:57.991449Z`。全程 attemptCount=1，没有第二 attempt或手工重发。

## 冻结与禁用边界

- exact guard 读回十二 Run running、Dataset Receipt=12、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、dev-org canary=0、九路 BH route current；判定为 `FAILED_FREEZE_BOUNDARY`，不自动重试。
- `pause-terminal` 仅在该 exact terminal、attemptCount=1 与上述零边界成立时执行，生成 definition rev106 disabled，
  hash `sha256:2bcc125ab27bacf87da8cef9ba043550cd4c5f23ca63da9e5e8dc1b3012bb0cc`；inspect 读回
  `configurationState=disabled / executionAuthorized=false / routingStatus=disabled / sourceReads=0`。
- snapshot worker 已停止，临时端口已释放，唯一外部 Runtime Host PID 29815 保持运行。本波没有商城源读取、
  没有手工重发、没有第二 attempt、没有 push，230 L0 继续挂起。

## 私有证据与回归

- 纯 HTTP preflight `863aff2e51952efc60a174299b62f212109eb629bacb715a93ef609bcb44e81c`；worker preflight/status
  `d6ff3a6fab3752042335883ee30a6e2adc34ce8ec58b90abaee1055fd33450a9` /
  `9038f171ff4eb024b13520c61725af935a93201fd64ede96f7e11c7b91b6689b`。
- prepare/schedule/controls `6fe1a9d6c9a8e694b6a875026ec96ba18bb3af0308e5ecc9a08f8f4c417fa8fe` /
  `d8efe032c58e163662838028d60a770770692d4612cfdc3b99cedb8d169d046c` /
  `c71be6bd39a5e7727ce12b345ae1029a89f6405e4c67f7c6d2a4dec2d3779a8b`。
- transfer/renew/enable `0a83c921034815d83f2c4cacbf0b4df7eb9b5a61e85c2f11499ee007dd8c8f51` /
  `e57f96b62b458b8e61416a486d9214040988eb6ba0f0dcae34644dad4f8e1405` /
  `62cd5471808f83db8acb112495f7fc795c136269e98018d1ae1c6f43d1d249b2`；pause-terminal
  `e8d61c4289c75f24e8c504f9906a60f8b1d7ea2227f59108b2d99bc0041d6434`。
- BH saved recovery、exact guard、supervisor 与 snapshot launcher 共 13 项专项回归通过；Python 编译与
  `git diff --check` 通过。实现、方案、终态与零副作用边界一致。

## 下一波

新增 BH terminal retirement 方案；只允许在 exact 单次 failed terminal、definition rev106 disabled、十二 Run
running、Store/link/projection 全零且 worker/18181 停止时执行正式 disable/fence/detach。verification 与提交完成后，
才可进入 BI direct successor。
