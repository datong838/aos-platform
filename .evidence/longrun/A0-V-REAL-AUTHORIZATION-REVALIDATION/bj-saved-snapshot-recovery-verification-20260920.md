# BJ 保存快照恢复、1800 秒预算与单 attempt 冻结验证

## 配置与 authority 转移

- definition rev109 disabled、BJ attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。外部 Runtime Host 唯一 PID 10991，第二 Host=0。
- prepare、schedule-ingest、controls 成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 在
  transfer 前已关闭并确认 18181 释放。
- transfer 生成 definition rev110 disabled，hash
  `sha256:69f74c8df4ab9ce2dadbb9468375262f5850eeac28dc17cd2a5cc8c34700114a`。
- renew 生成 recovery rev36，hash
  `sha256:9573fdb29e10d0306541b5f7c2cdb813c240088bff7141188e8f4a526b44c73e`，同事务生成
  definition rev111 enabled，hash
  `sha256:a4b5985a2f8c1f5c876f1aac24f09b8efe19ecc0f97b2ac4bb174425acba021f`；enable 读回
  `executionAuthorized=false / original_group_pending / sourceReads=0`。

## 唯一自然 attempt 与有界停止

- exact lease `A0V-BJ-SNAPSHOT-WORKER-20260920` 建立后，supervisor 启动唯一自然 worker PID 27166；
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一 attempt `6746bf55-daf2-4bc6-a8fe-038f3ff0bcba`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它健康续租至 revision60。
- supervisor 以数据库 `accepted_at` 为起点，在 elapsed=1801 秒命中预算，只向 exact worker 进程组发送
  一次 SIGTERM；18181 随即释放，但进程未在180秒排空预算内退出，supervisor 按 fail-closed 报错。
- 只读对账确认同一 attempt 于 revision61 正式收敛为 `abandoned / ATTEMPT_LEASE_EXPIRED`，
  `completedAt=2026-09-20T05:39:37.172964Z`。残留 PID 27166 在恢复升级前自行退出，故未发送 SIGKILL；
  attemptCount始终为1，没有第二 attempt或手工重发。
- 本波启动命令沿用了2秒内部只读安全轮询，外层按最长50秒持续采样；落盘版本已把默认观察间隔收紧为
  50秒，供后续波次遵守。该偏差未产生写动作、重复 attempt 或额外 worker。

## 冻结与禁用边界

- exact guard 读回十二 Run running、Dataset Receipt=12、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、dev-org canary=0、九路 BJ route current；判定 `ABANDONED_FREEZE_BOUNDARY`。
- `pause-terminal` 仅在 exact terminal、attemptCount=1 与零副作用边界成立时执行，生成 definition rev112
  disabled，hash `sha256:e7778230b85c15b11255d6f2d2e54c302239ba5957e97dab918557bdfbce13b1`，
  `sourceReads=0`。
- snapshot worker 已停止，18181 无临时监听，唯一外部 Runtime Host PID 10991 保持运行。本波没有商城源读取、
  没有手工重发、没有第二 attempt、没有 push，230 L0 继续挂起。

## 私有证据与回归

- 纯 HTTP preflight `f206f207fce3771750ee741db9fc7a8547708fcf58af58b16b33e6bb8122f667`；worker
  preflight/status `a06bbcda83466bc141051adb19625d2d0a993d124657bc69c9b5c87b8e5ce27f` /
  `8933006aa3a7541c9049e8b1db36b0aa10b1889b255c10ca29321c6655c371a7`。
- prepare/schedule/controls `4304d68c0727138a3140c90ccf9bd1d0fdd7dbf956fc0aa7988fb6c46a442d9c` /
  `6e3f6c3235858237a1b159e9643d92ea855ad31debd95d8e89acd99fa25a0935` /
  `8c0be82edc6bd26f9e2312baad71ae8a05af1e78f22da01c5a321335f489b386`。
- transfer/renew/enable `107f183356db19f7c54495001d0932665b25a563afcd291c8df5c34af6b51a14` /
  `a570e12598c8ce01e97c961e76c5aa4b2128b28d59f3324bab2ee73546330f10` /
  `6c385d6a6229a46dfb10bde30242c08a2b24215f1bc417c98a4fe3d3360dc705`；pause-terminal
  `61ba53c364dbbbd6f73bc8cc129e2fde112c70eb6df1c1d43083d97eddbb2e80`。
- BJ saved recovery、exact guard、supervisor 与 snapshot launcher 专项回归通过；Python 编译与
  `git diff --check` 通过。实现、方案、终态与零副作用边界一致。

## 下一波

新增 BJ terminal retirement 方案；仅在 exact 单次 abandoned terminal、definition rev112 disabled、十二 Run
running、Store/link/projection 全零且 worker/18181 停止时执行正式 disable/fence/detach。verification 与提交后，
才可进入 BK direct successor。
