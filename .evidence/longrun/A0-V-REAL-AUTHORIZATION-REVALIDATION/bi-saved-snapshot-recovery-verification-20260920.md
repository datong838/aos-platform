# BI 保存快照恢复、1800 秒预算与单 attempt 冻结验证

## 配置与 authority 转移

- definition rev106 disabled、BI attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。外部 Runtime Host 唯一 PID 10991，第二 Host=0。
- prepare、schedule-ingest、controls 成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 在
  transfer 前已关闭并确认 18181 释放。
- transfer 生成 definition rev107 disabled，hash
  `sha256:0a5d0cb17cddeeb3fcddfdbee61d6e748d2e90f83841d3362b590cfe6e9841e9`。
- renew 生成 recovery rev35，hash
  `sha256:f72f139bfad326d503d77617732bb9baf029e6c53114293b9c590aedeafd7dd6`，同事务生成
  definition rev108 enabled，hash
  `sha256:8eddeeafb955427dd39228f5aa2f81c77b2dc8f001d4a3443960f3877a0af362`；enable 读回
  `executionAuthorized=false / original_group_pending / sourceReads=0`。

## 唯一自然 attempt 与有界停止

- exact lease `A0V-BI-SNAPSHOT-WORKER-20260920` 建立后，supervisor 启动唯一自然 worker PID 16679；
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一 attempt `1f8e44c0-c5a7-4099-89a0-6f4998589e4e`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它健康续租至 revision60。
- supervisor 以数据库 `accepted_at` 为起点，在 elapsed=1801 秒命中预算，只向 exact worker 进程组发送
  一次 SIGTERM；有界排空确认 return code -15、`workerStopped=true`。
- 同一 attempt 于 revision61 正式收敛为 `abandoned / ATTEMPT_LEASE_EXPIRED`，
  `completedAt=2026-09-20T04:28:01.120133Z`。全程 attemptCount=1，没有第二 attempt或手工重发。

## 冻结与禁用边界

- exact guard 读回十二 Run running、Dataset Receipt=12、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、dev-org canary=0、九路 BI route current；判定 `ABANDONED_FREEZE_BOUNDARY`。
- `pause-terminal` 仅在 exact terminal、attemptCount=1 与零副作用边界成立时执行，生成 definition rev109
  disabled，hash `sha256:0559aefc6ae859f1ce1306bf6e34312555c6580173243108b96244c6f4a1b124`，
  `sourceReads=0`。
- snapshot worker 已停止，18181 无临时监听，唯一外部 Runtime Host PID 10991 保持运行。本波没有商城源读取、
  没有手工重发、没有第二 attempt、没有 push，230 L0 继续挂起。

## 私有证据与回归

- 纯 HTTP preflight `370c10689d7adabf6c5fd87a5e780b4325bbc77866ea15d2718f4e72c4ff1bf1`；worker
  preflight/status `670acf8ab5ec5c0e52b7bbc1b61dfce60567aba2fc01a009f92329259bafa18d` /
  `4db2707bd7c21366b32f12d48b813881a454e12ba2ac1aaf164fa196fba5c6ff`。
- prepare/schedule/controls `3b9bcebd16e452cee891427083ac9255b55476f2183c258c75f3011adfc42be8` /
  `df4b39ddf084b81176381702cf1be396c3e638d8eb3c4f3c4b385a7fda71eae4` /
  `f63610a2a4b188378ac1e4520c235634f75dcfaf1c30178b3a7f071757ee2ff6`。
- transfer/renew/enable `2c23d888e45e9db8f32dad31d50d6de17d86fad47519f71b867fc7facac4104f` /
  `4569ba18fdf43fbee4858893c926c47d1085042f4d82f40ce6ec4c51c0f7a2cc` /
  `b541dcf3aadcef4a9436ddddd4cd132b3525308c90cf14c6952bd8612f8228b8`；pause-terminal
  `b85713d54b94ce40f92eec80600eb4e83190df60e3d5c00d2b9c02ee20e8c1e2`。
- BI saved recovery、exact guard、supervisor 与 snapshot launcher 专项回归通过；Python 编译与
  `git diff --check` 通过。实现、方案、终态与零副作用边界一致。

## 下一波

新增 BI terminal retirement 方案；仅在 exact 单次 abandoned terminal、definition rev109 disabled、十二 Run
running、Store/link/projection 全零且 worker/18181 停止时执行正式 disable/fence/detach。verification 与提交后，
才可进入 BJ direct successor。
