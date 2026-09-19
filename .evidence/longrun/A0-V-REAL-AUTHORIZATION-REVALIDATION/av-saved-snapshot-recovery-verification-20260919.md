# AV 保存快照恢复、1800 秒终态与冻结验证

## 配置与 authority 转移

- 纯 HTTP 18181 阶段读回：DB migration disabled、QYH Cron=false、snapshot worker=false、
  进程内 Runtime Host=false；系统仅有 launchd Runtime Host PID 8154，AV attempt=0。
- prepare、schedule-ingest、controls 均为 `sourceReads=0`，十二 schedule 保持 disabled；纯 HTTP 端口
  在 transfer 前已释放。
- definition 的实际 owner 仍是 AT rev73 disabled，而运行时正式后继链为 AT→AU→AV。
  Owner 新增有限、无环、租户内 exact `currentInstallationRef` 链校验，并逐节点验证 runtime
  disabled/fenced、正式 detach 与 3/3 resources released；一跳原合同保持。
- transfer 产生 definition rev74 AV disabled，hash
  `sha256:4d82a3e0202f816a6e9a7e8d35cb8ce82b0e73d2835267c21607bc5df998966c`。
- renew 产生 recovery rev24，hash
  `sha256:816768cae29a65e52fc08969ed1ede533661decdac6708cdfe80a8174a7015b3`；同一事务产生
  definition rev75 enabled，hash
  `sha256:6c042f13d71dc3f9409949816381e0af936dbf0d595acd3930b6af8e5c0c956b`。全部结果
  `sourceReads=0`。

## 自然 worker 与唯一 attempt

- 首次 worker 启动在任何业务执行前被过期 `SC4-5L6Y6C-SPLIT-WORKER-20260916` lease
  门禁拒绝，attempt 仍为 0。原任务 Delivery Receipt 明确“重启须新部署 lease”，因此创建窄范围
  `A0V-AV-SNAPSHOT-WORKER-20260919` lease，启动器只接受该 exact 任务。一次系统 Python
  导入失败也发生在 worker 生命周期之前；改用仓库固定 venv 后启动。
- 启动读回 snapshot worker=true/topology=independent、Runtime Host=false、Cron=false；唯一外部
  Runtime Host 仍为 PID 8154，且读回 `recoverableStoreExecutionLimitSeconds=1800`。
- 自然 worker 产生唯一 AV attempt `42717b1a-1d3b-442d-9b18-683593e4bbbf`，
  idempotency key `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。
- attempt 持续 heartbeat/Lease 并越过旧 300 秒上限；第 1809 秒仍为健康 running。随后 heartbeat
  停止，Lease 到期后于 `2026-09-19T11:08:02.896229+00:00` 正式终结为 rev61
  `abandoned / ATTEMPT_LEASE_EXPIRED`，无 terminal error type。
- 终态边界：attemptCount=1；12 Runs 仍 running，12 Dataset Receipt 保留；relationship=1、
  link command=1、linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、
  projection pending=0、`dev-org/dev-project` canary=0。

## 冻结与停止边界

- 在终态读回后立即停止自然 worker；18181 已释放，workerState=STOPPED、workerTaskAlive=false，
  未生成第二 attempt。
- `pause-terminal` 仅在上述 exact abandoned 与全零 Store 边界下执行，原子将 definition
  rev75 推进为 rev76 disabled，hash
  `sha256:d73f45ea3c439891cdaec17130ba47044aa1932d13fc29b43dc8ae1f2db3d2cb`，
  `sourceReads=0`。该终态不授权重发、手工 `run_definition` 或自然 successor。
- 本波未读取商城源数据、未 push、未修改其他分支；230 L0 继续挂起。

## 验证

- Owner 真实 PG、AV saved recovery、AV attempt guard 与 snapshot launcher 组合回归：`37 passed`。
- 终态新增合同与 guard 复核：`12 passed`。
- Python 编译与 `git diff --check` 通过。

## 下一波

以 AV 唯一 abandoned attempt、definition rev76 disabled 和零 Store 提交边界为唯一上位权威，
方案先行完成 AV 正式 retirement/detach，再创建 AW direct successor。禁止在 AV 内继续自然执行。
