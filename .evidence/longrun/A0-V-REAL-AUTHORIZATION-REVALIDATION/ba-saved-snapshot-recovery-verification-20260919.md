# BA 保存快照恢复、单 attempt 终态与冻结验证

## 配置与 authority 转移

- definition rev82 disabled、BA attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev82 disabled 生成 BA rev83 disabled，hash
  `sha256:c8b8e22405ef8f1a5ef546ae07be00d333ec041a40394c0f184d7eeed0eee7a5`。
- renew 从 recovery rev26 生成 rev27，hash
  `sha256:1f199dc3790539c068c33211d1ebe0028666b1d79e337b8c3b20aace7f2d24c6`；同一事务生成
  definition rev84 enabled，hash
  `sha256:36cc0055be5e3ca9257d36d43c8819aab1e117ec1efeb4c4ee9f419b59dd7c4a`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与唯一终态

- 创建 exact `A0V-BA-SNAPSHOT-WORKER-20260919` deployment lease 后启动唯一自然 snapshot worker；读回
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一自然 attempt `a000b48d-52d5-44ce-a3c5-159b40b1f9b6` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision 60，
  最终于 `2026-09-19T15:42:19.346664+00:00` 正式收敛为 revision 61
  `abandoned / ATTEMPT_LEASE_EXPIRED`。
- 2 秒只读监督在 terminal 落库后核验 exact worker PID 36991，再发送 SIGINT；18181 随即释放，未产生第二
  attempt。进程短暂滞留，exact TERM 后退出，无需 KILL；worker 状态最终为 STOPPED/taskAlive=false。
- exact guard 固定验证 attemptCount=1、十二 Run 仍 running、十二 Dataset Receipt 保留；relationship=1、
  link command=1、linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、
  projection pending=0、BA 九路与三资源保持、`dev-org/dev-project` canary=0。

## 冻结结果

- `pause-terminal` 在唯一 `ABANDONED_FREEZE_BOUNDARY` 下把 definition rev84 推进为 rev85 disabled，hash
  `sha256:9c1c2ab51ae9e18db8231638687d28a9d8c57ed96352aa59bcc8078ad67f7297`；最终读回
  disabled/executionAuthorized=false/routingStatus=disabled，`sourceReads=0`。
- snapshot worker 已停止、18181 无监听；唯一外部 Runtime Host PID 29815 继续运行。本波没有商城源读取、
  没有手工重发、没有切换幂等键、没有 push，230 L0 继续挂起。

## 计划偏差与风险

- 为消除 terminal 到人工轮询之间产生第二 attempt 的窗口，15:14 将只读 monitor 重启为“terminal 后自动停止
  exact PID”的监督链。重启同时重置了 monitor 自身的 1800 秒计时，导致 attempt 的最终 elapsed 为 1909 秒，
  比方案写明的 1800 秒上限多 109 秒。这是监视预算偏差，不能记为完全按时执行。
- 偏差期间 attempt 始终健康续租、attemptCount=1，十二 Run/Receipt 和 Store/link/projection/canary 边界未变化；
  正式终态为 Lease 过期后的 abandoned，不是未知结果。rev85 disabled 已消除继续领取窗口。
- 后续退休波必须以 exact rev61 abandoned + definition rev85 disabled 为 authority，方案中显式接受上述预算偏差，
  不得在 BA 内恢复 worker 或创建第二 attempt。

## 证据与验证

- BA recovery 状态结果 SHA-256：prepare
  `65018414c3a1889cfe268e825f07a8b580ab71d6fdcdd49081ad8290bd3c498e`、schedule
  `cbc78997aba621092e7edc7bc8ae1a5003d2e5f9286cc6390b4ecc84ad808ab3`、controls
  `93500afa33a0d11aefc7be5f5e09deb4285b4d94a7454d2beb9f69306eedd0a1`、transfer
  `3c348225de94b5483659da82d431967f0f60e819f30d9b9fe14fc48add5d3613`、renew
  `33755a519cb0bc20ee665c3de2164a6a1b21c9a80161ce65b9af002e94c6b6e5`、enable
  `599a49ebdbe30543e33bb90bd60ddbca48bbb4f00520b8e0237a0777b1fe8af3`、pause
  `c0cd3defa118295bfc122fa2c693f5b22fca1a417f06ee718d209fe50f248b85`。
- 纯 HTTP preflight hash
  `35458d3706420248d44392ae97a84ffeac217acd5530434093ec17111fece423`；snapshot worker preflight hash
  `c12ed12b173695d582252f54994873d436d4fe8ced235bdd4774367ce983ec26`。
- BA saved recovery、exact guard、terminal monitor 与 snapshot launcher 组合回归 `13 passed`；Python 编译通过。

## 下一波

新增 BA terminal retirement 方案；只允许在 exact 单次 abandoned、definition rev85 disabled、十二 Run running、
Store/link/projection 全零且 worker/18181 停止的边界下执行正式 retirement。verification 与提交完成后，才可进入
BB direct successor。
