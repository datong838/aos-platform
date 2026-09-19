# BB 保存快照恢复、单 attempt 终态与冻结验证

## 配置与 authority 转移

- definition rev85 disabled、BB attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev85 disabled 生成 BB rev86 disabled，hash
  `sha256:916e9dfe66ff574c6e53b74ad50c9123124b8c2752237c03a98f16d824856741`。
- renew 从 recovery rev27 生成 rev28，hash
  `sha256:85694eec74f716752544854abb1b021148da4075de615d37cee2d49101f566b6`；同一事务生成
  definition rev87 enabled，hash
  `sha256:966018ac81d1f52f2930e002f2cdd1b028ca95b281ec475522cc58d1b0039a87`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与唯一终态

- 创建 exact `A0V-BB-SNAPSHOT-WORKER-20260920` deployment lease 后启动唯一自然 snapshot worker；读回
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一自然 attempt `ee8dfb28-6b51-47da-9003-2c70d51ea08e` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision 60；
  只读 monitor 以数据库 `accepted_at` 为起点，在 elapsed=1800 秒读回
  `ATTEMPT_ELAPSED_BUDGET_EXHAUSTED` 后只向 exact worker PID 44964 发送 SIGINT，未重置预算。
- 18181 随 SIGINT 立即释放；进程完成 JDBC 清理后仍滞留，exact TERM 等待 15 秒仍未退出，最终仅对已复核同一
  命令的 PID 44964 使用 KILL。唯一外部 Runtime Host PID 29815 未受影响，也未产生第二 attempt。
- worker 停止后，同一 attempt 于 `2026-09-19T16:48:06.308752+00:00` 正式收敛为 revision 61
  `abandoned / ATTEMPT_LEASE_EXPIRED`。终态 elapsed=1909 秒包含 worker 精确停止后等待既有 lease 到期的 109 秒，
  不是 worker 超出 1800 秒执行预算。
- exact guard 固定验证 attemptCount=1、十二 Run 仍 running、十二 Dataset Receipt 保留；relationship=1、
  link command=1、linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、
  projection pending=0、BB 九路与三资源保持、`dev-org/dev-project` canary=0。

## 冻结结果

- `pause-terminal` 在唯一 `ABANDONED_FREEZE_BOUNDARY` 下把 definition rev87 推进为 rev88 disabled，hash
  `sha256:fa48049dac9b2936884acaedad0783068e4eb9be08ccf019ae19f9ab94a18556`；最终读回
  disabled/executionAuthorized=false，`sourceReads=0`。
- snapshot worker 已停止、18181 无监听；唯一外部 Runtime Host PID 29815 继续运行。本波没有商城源读取、
  没有手工重发、没有切换幂等键、没有 push，230 L0 继续挂起。

## 计划偏差与风险

- worker 在精确 elapsed=1800 秒停止，满足方案的有界预算；终态在 lease expiry 后落库，因此终态 elapsed=1909
  秒是预期的冻结等待，不构成执行预算偏差。
- worker 收到 SIGINT 并释放 18181 后仍滞留，TERM 亦未使其退出，最终需要 exact KILL。操作仅针对已复核 PID
  与命令行；Runtime Host 和其他进程未受影响。后续 launcher 仍应调查清理阶段不能自然退出的原因。
- 后续退休波必须以 exact rev61 abandoned + definition rev88 disabled 为 authority，不得在 BB 内恢复 worker
  或创建第二 attempt。

## 证据与验证

- BB recovery 状态结果 SHA-256：prepare
  `38b1cec03a447b40fcd7f60b11fd399a153bedf476b044fef106dbf053ee0e65`、schedule
  `e8246546943e62602fe134a2e1601023f48503ac627be16ba643b978e5de821a`、controls
  `0eaf7362f098b0daccde13f0acb3c98ba1f97c5d54cd490c935c59092ac8c40d`、transfer
  `beabdbcfa8911fbd2d2ad29e49beae8744af45e26fa5b9071b5f75567e1df669`、renew
  `c32b1d85b8b406bbaeb27c9908b11f3aa376816746d0c92f31a4797d7e7e0254`、enable
  `81648819b0673e6512b736a2db0b38c6ab334d3561c16827d3fc0b277f2c3477`、pause
  `81babe754394ab37d6d3e591d258fc97de0f63e956639b5e7c163b1f7d499465`。
- 纯 HTTP preflight hash
  `84af80160121de5d6a0d9fc75e76f2e9cf5329851a843aa6f4230b842923f9ed`；snapshot worker preflight hash
  `c308da54f8cfcde30a72831484207edfc712641838b89f07634b708f28ece0ea`。
- BB saved recovery、exact guard、terminal monitor 与 snapshot launcher 组合回归 `12 passed`；Python 编译通过。

## 下一波

新增 BB terminal retirement 方案；只允许在 exact 单次 abandoned、definition rev88 disabled、十二 Run running、
Store/link/projection 全零且 worker/18181 停止的边界下执行正式 retirement。verification 与提交完成后，才可进入
BC direct successor。
