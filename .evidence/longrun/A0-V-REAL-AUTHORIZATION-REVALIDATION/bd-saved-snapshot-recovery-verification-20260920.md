# BD 保存快照恢复、单 attempt 终态与冻结验证

## 配置与 authority 转移

- definition rev91 disabled、BD attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev91 disabled 生成 BD rev92 disabled，hash
  `sha256:7bf8bbfb0cedfc23d76a046f0fb21d3225fdcac444d95322d6528cdb101c42d0`。
- renew 从 recovery rev29 生成 rev30，hash
  `sha256:77cd78550215177e1ae0be5d1f4096cc0f65713ec5395fe7a8fe859f4b915b98`；同一事务生成
  definition rev93 enabled，hash
  `sha256:608680b4d71afa3f369df03b197fce3ddda4df5c4ab4f09a3c99f2882e2f2da3`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与唯一终态

- 创建 exact `A0V-BD-SNAPSHOT-WORKER-20260920` deployment lease 后启动唯一自然 snapshot worker；读回
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一自然 attempt `f1e89789-86ca-4cd5-9854-c75e1c41db94` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision 60；
  只读 monitor 以数据库 `accepted_at` 为起点，在 elapsed=1799 秒先读回正式 terminal，随即只向 exact worker
  PID 58816 发送 SIGINT，未重置预算。
- worker 随 SIGINT 自然退出，18181 释放，无需 TERM/KILL；唯一外部 Runtime Host PID 29815 未受影响，也未产生
  第二 attempt。
- 同一 attempt 于 `2026-09-19T20:34:22.982970+00:00` 正式收敛为 revision 61
  `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`。数据库
  `completed_at-accepted_at=1798` 秒，严格小于 1800 秒预算。
- exact guard 固定验证 attemptCount=1、十二 Run 仍 running、十二 Dataset Receipt 保留；relationship=1、
  link command=1、linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、
  projection pending=0、BD 九路与三资源保持、`dev-org/dev-project` canary=0。

## 冻结结果

- `pause-terminal` 在唯一 `FAILED_FREEZE_BOUNDARY` 下把 definition rev93 推进为 rev94 disabled，hash
  `sha256:8c7f7835c3a4107471f8bc5232822e3da29bceac458861561061ea6d4db4204b`；最终读回
  disabled/executionAuthorized=false，`sourceReads=0`。
- snapshot worker 最终 STOPPED/taskAlive=false、18181 无监听；唯一外部 Runtime Host PID 29815 继续运行。
  本波没有商城源读取、没有手工重发、没有切换幂等键、没有 push，230 L0 继续挂起。

## 计划偏差与风险

- terminal 在 elapsed=1799 秒先于 1800 秒预算发生，监督按“terminal 与预算先到者立即停 worker”执行，符合方案。
- 纯 HTTP 就绪探测误用了不存在的 `/health` 路径，产生 10 次只读 404；端口监听、serve preflight flags 与后续
  12 个 schedule HTTP 200 共同完成就绪证明，未产生写入或业务副作用。
- 本波执行与证据边界无未知提交；后续退休波必须以 exact rev61 failed + definition rev94 disabled 为 authority，
  不得在 BD 内恢复 worker或创建第二 attempt。

## 证据与验证

- BD recovery 状态结果 SHA-256：prepare
  `668014163c754b7a0b240d42c69d6be51e874beeab49e719438796622403f4c3`、schedule
  `c592e4e59d396af08dec4dcb26581690b08ca17d0b2a53baf7cdfda77feadc63`、controls
  `8493a50d7adcc7fe352688b42b7f17b8513bfecb2daf54a00116b6d817023d87`、transfer
  `059c1930128f4b5fe4d4a6fc4c23f6043d5df98a924865ef20d96d852c11028b`、renew
  `8321b6317591290d4a3519d6969d56b241a53abe915234dda034f3f746732167`、enable
  `1a93efe9c69a5e6c0fd14e4e6c447abd2194f8b4b28ebdf9fc1410de8ce83c23`、pause
  `cfc1b99ab1a434a9f7c1296a50a3e02e155ca496feb2418f4a690a7f622ccd3c`。
- 纯 HTTP preflight hash
  `b2ad70d87f27fee5b1d0d5a55226441313451fb20a1486b2885cbf5e972d2f26`；snapshot worker preflight hash
  `88f07aac0aee13f3c2d9afa9d7e5017c88d8062081604e74ef2b46e15cc6ee21`。
- BD saved recovery、exact guard、terminal monitor 与 snapshot launcher 组合回归 `12 passed`；Python 编译与
  `git diff --check` 通过。

## 下一波

新增 BD terminal retirement 方案；只允许在 exact 单次 failed、definition rev94 disabled、十二 Run running、
Store/link/projection 全零且 worker/18181 停止的边界下执行正式 retirement。verification 与提交完成后，才可进入
BE direct successor。
