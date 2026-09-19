# AX 保存快照恢复、1800 秒终态与冻结验证

## 配置与 authority 转移

- 纯 HTTP 18181 阶段读回：DB migration disabled、QYH Cron=false、snapshot worker=false、
  进程内 Runtime Host=false；系统中第二 Runtime Host=0，AX attempt=0。
- prepare、schedule-ingest、controls 均为 `sourceReads=0`，十二 schedule 保持 disabled；纯 HTTP 端口
  在 transfer 前已释放。
- transfer 从 definition rev76 disabled 生成 AX rev77 disabled，hash
  `sha256:45b58f70cc4b679827878405641d29e6d89757f0b4db3e01c632183ee2b5465b`。
- renew 从 recovery rev24 生成 rev25，hash
  `sha256:4396a3ff65d4e57fb856ad5c32d580932a1b4ee9f9b3a469504da10a197ec75c`；同一事务生成
  definition rev78 enabled，hash
  `sha256:a6c66e389358909072b4af1859909472da263eca0e1c033a54ad0774e47b113d`。执行未提前开始，
  enable 读回 `executionAuthorized=false / original_group_pending`，全部结果 `sourceReads=0`。

## 自然 worker 与唯一 attempt

- 创建窄范围 `A0V-AX-SNAPSHOT-WORKER-20260919` deployment lease；启动器只接受该 exact task、m1、
  ACTIVE、未过期四项合同，并使用 AX 私有状态目录。启动读回 snapshot worker=true/topology=independent、
  Runtime Host=false、Cron=false；独立正式 Runtime Host 保持唯一。
- 自然 worker 产生唯一 AX attempt `e5b99486-ecf6-460e-b2d3-de40e372d7c9`，idempotency key
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`；未调用
  `run_definition`，未生成第二 attempt。
- attempt 持续 heartbeat/Lease 并越过旧 300 秒失败点。第 1767 秒仍为 healthy running；于
  `2026-09-19T13:03:26.025692+00:00`、约第 1818 秒正式终结为 revision 61
  `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`。
- 终态边界：12 Runs 仍 running、12 Dataset Receipt 保留；relationship=1、link command=1、
  linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、projection pending=0；
  AX 九路与三资源保持，`dev-org/dev-project` canary=0。

## 冻结与停止边界

- 终态后立即停止自然 worker；18181 已释放，workerState=STOPPED、workerTaskAlive=false，未生成第二 attempt。
- 首次 `pause-terminal` 在任何写入前被旧 AV guard 身份拒绝，definition 仍为 rev78 enabled；补充 AX exact guard
  接线与 failed/abandoned 冻结结果合同，23 项 RED→GREEN 组合回归通过后，使用同一 pause key 重试。
- `pause-terminal` 在 exact failed 与全零 Store 边界下将 definition 原子推进为 rev79 disabled，hash
  `sha256:2cfb50c609a545efb530773e4aeede231f0333dce4f28bf587f46920dadb2551`，`sourceReads=0`。
  最终 inspect 读回 `configurationState=disabled / executionAuthorized=false / routingStatus=disabled`。
- 本终态不授权重发、手工 `run_definition` 或在 AX 内继续自然执行；下一步只能正式 retirement/detach 后创建
  direct successor。本波未读取商城源数据、未 push、未修改其他分支；230 L0 继续挂起。

## 证据与验证

- transfer/renew/enable/pause 私有结果文件 SHA-256 依次为
  `552795aa993ff2cf6bfe055f00bb9da4217460993a7d5a0cdd3c27a8d78c82c2`、
  `d202a6df072b3c98d085979c2c8487b0c76de8ac6c973a67e9db291c6652f295`、
  `8207eac59ee75b12fdda0451e9e1bbfd92f193e86b4d5413d65923f52d40c446`、
  `fcb54e663d84ec6e26fcb6f0c5da5c9e5e7aa9a2c287cc5bab6b0c96a885474f`。
- AX/AV saved recovery、AX/AV guard、snapshot launcher 与 definition Owner 组合回归 `49 passed`；
  Python 编译与 `git diff --check` 通过。

## 下一波

以唯一 failed attempt、definition rev79 disabled 和零 Store 副作用为唯一上位权威，方案先行完成 AX 正式
retirement/detach；要求九路回 legacy、三资源 released、无 running/unknown/pending、canary=0。随后仅从 exact
detach Receipt 创建 AY direct successor，禁止在 AX 内重发。
