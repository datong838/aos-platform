# BC 保存快照恢复、单 attempt 终态与冻结验证

## 配置与 authority 转移

- definition rev88 disabled、BC attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev88 disabled 生成 BC rev89 disabled，hash
  `sha256:337d2d2c5f87655b0ef0fc009b80971ee5820c3f3fb7c2ca2d51da68fa68d6c2`。
- renew 从 recovery rev28 生成 rev29，hash
  `sha256:f6414561a1989b64b5fa08cfbbcc3f108a319c37155e72e6d49c0fa82c24696b`；同一事务生成
  definition rev90 enabled，hash
  `sha256:e7aecc3be31f2428909c4442b1e2ad914974a8929849a8dc68cd364b93b92464`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与唯一终态

- 创建 exact `A0V-BC-SNAPSHOT-WORKER-20260920` deployment lease 后启动唯一自然 snapshot worker；读回
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一自然 attempt `3ab54352-408c-4aae-a150-fb23c64cd7b7` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision 60；
  只读 monitor 以数据库 `accepted_at` 为起点，在 elapsed=1800 秒读回
  `ATTEMPT_ELAPSED_BUDGET_EXHAUSTED` 后只向 exact worker PID 52681 发送 SIGINT，未重置预算。
- worker 随 SIGINT 自然退出，18181 释放，无需 TERM/KILL；唯一外部 Runtime Host PID 29815 未受影响，也未产生
  第二 attempt。
- 同一 attempt 于 `2026-09-19T19:03:48.139404+00:00` 正式收敛为 revision 61
  `abandoned / ATTEMPT_LEASE_EXPIRED`。数据库 `completed_at-accepted_at` 为 1893 秒，其中 worker 精确停止后等待
  原 lease 到期 93 秒，不是 worker 超出 1800 秒执行预算。稍后只读 guard 的动态 elapsed 使用
  `clock_timestamp()-accepted_at`，显示的更大观察年龄不作为终态执行时长。
- exact guard 固定验证 attemptCount=1、十二 Run 仍 running、十二 Dataset Receipt 保留；relationship=1、
  link command=1、linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、
  projection pending=0、BC 九路与三资源保持、`dev-org/dev-project` canary=0。

## 冻结结果

- `pause-terminal` 在唯一 `ABANDONED_FREEZE_BOUNDARY` 下把 definition rev90 推进为 rev91 disabled，hash
  `sha256:f52a1850ade51f783d9040ea3f48b7d4ca866ae63880242ae5de7171d510252a`；最终读回
  disabled/executionAuthorized=false，`sourceReads=0`。
- snapshot worker 最终 STOPPED/taskAlive=false、18181 无监听；唯一外部 Runtime Host PID 29815 继续运行。
  本波没有商城源读取、没有手工重发、没有切换幂等键、没有 push，230 L0 继续挂起。

## 计划偏差与风险

- worker 在精确 elapsed=1800 秒停止，满足方案的有界预算；终态在 lease expiry 后落库，因此终态 elapsed=1893
  秒是预期的冻结等待，不构成执行预算偏差。
- 本波执行与证据边界无未知提交；后续退休波必须以 exact rev61 abandoned + definition rev91 disabled 为
  authority，不得在 BC 内恢复 worker或创建第二 attempt。

## 证据与验证

- BC recovery 状态结果 SHA-256：prepare
  `54adac626d8a299bc33b18b19d59fdbe36abba20f09486df1e41abb1f2befffd`、schedule
  `7ba7325aca25dbed344dc124967cb9ab060a658d02578a2eafa4602517afa7e4`、controls
  `060bab18f0c460fd44b95df485b856d81dbd9d8511d90086b51bb31fbc19c452`、transfer
  `3daf0b63acc5192d2f226684fec342b6271ebcffa0527ba39129cb7672757a4a`、renew
  `5414cfd14cab4d52a5943b4053661adce3b5561a90ca2c24f9fcfa01d29ca349`、enable
  `7cc29e35cef28e12226913b869e09e81141d7fff1c3fc1bfa6f7f01d121fbfe4`、pause
  `3f32af92da02d8023cdfccf4caa0b38ebfec0930c210f48644934740028530a7`。
- 纯 HTTP preflight hash
  `7d7ca2083d98833b0157eac51424ee450713b520f673f86758c55538b950b42a`；snapshot worker preflight hash
  `69e16b438d21387fc3d8616844ecaa9107ba5351147de99ac7d673b4d821f897`。
- BC saved recovery、exact guard、terminal monitor 与 snapshot launcher 组合回归 `12 passed`；Python 编译通过。

## 下一波

新增 BC terminal retirement 方案；只允许在 exact 单次 abandoned、definition rev91 disabled、十二 Run running、
Store/link/projection 全零且 worker/18181 停止的边界下执行正式 retirement。verification 与提交完成后，才可进入
BD direct successor。
