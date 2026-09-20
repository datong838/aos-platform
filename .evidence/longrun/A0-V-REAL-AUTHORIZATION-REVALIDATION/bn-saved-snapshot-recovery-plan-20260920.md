# BN 保存快照恢复与单一自然 attempt 方案（2026-09-20）

## 1. 当前权威

- HEAD `751a3bc1`；BN installation `d89bca67-4472-4b43-b0bd-ae8a2e0459f5` /
  generation `a43b3e64-7bb4-454c-822e-58bc13acbcaa` 已完成九路切换与 12 次新增健康续租。
- binding rev6/epoch3 enabled/ready/unfenced，route rev165/group192；definition rev118 disabled，
  BN attempt=0。
- 十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、
  runtime pending 与 canary 均为 0。本波只转移冻结输入，不读取商城源数据，不调用
  `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述 BN、definition rev118、attempt=0、十二 Run/Receipt 与零副作用边界；
   确认单写者 m1 和一个外置 Runtime Host。
2. **纯 HTTP 18181**：启动一个受控纯 HTTP API，读回 Cron=false、snapshot worker=false、进程内
   Runtime Host=false；外置 Runtime Host保持恰好一个，第二 Host=0。只允许 HTTP，不允许 snapshot
   worker 或 definition 执行。
3. **冻结输入转移**：prepare、schedule-ingest、controls；关闭 18181 并确认端口释放；从 BL
   rev118 disabled/recovery rev38 执行 transfer -> BN rev119 disabled、renew -> recovery rev39 /
   definition rev120 enabled，enable 读回 `sourceReads=0`。
4. **唯一自然 worker**：以 exact lease 启动同一个 supervisor/worker；固定 BN installation、
   generation、definition rev120、recovery rev39、数据库 accepted_at 与 request hash。禁止手工
   `run_definition`、第二 worker、第二 Runtime Host或第二 attempt。
5. **单轮观察窗**：每 50 秒只读采样唯一 attempt，直到正式 terminal；若 300 秒出现
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且十二 Run仍 running、Store Receipt=0、
   `ecom_link`=0、projection pending=0，则不重发，在原 accepted_at 起算的 1800 秒有界预算内继续
   同一 attempt。unknown 只冻结边界，不猜测成功。
6. **终态/verification/commit**：正式终态及零副作用读回后，pause-terminal -> definition rev121
   disabled；若进程需停止，先 SIGTERM，有界 180 秒后仅在 exact terminal/attemptCount=1/零副作用/
   PID 与进程组精确匹配时允许一次 SIGKILL。落盘 verification、测试、精确提交，然后自动进入
   failed/terminal retirement + direct successor 波。

## 3. 停止条件

- 任一 identity、Receipt/hash、definition/recovery revision、十二 Run/Receipt 或 route/binding 漂移；
- Cron、snapshot worker 或 Runtime Host 在纯 HTTP 阶段被启用；出现第二 Host/worker/attempt；
- 商城源读取、`dev-org/dev-project` 非零写、Store Receipt/ecom_link/projection pending；
- 未知提交边界、手工 `run_definition`、300 秒失败后重发或更换 idempotency key。

所有非人工决策型工程阻断由当前唯一开发在上述边界内自行诊断、最小修复与继续；不 push、不动其他
分支，230 L0 继续挂起。

## 4. 执行中纠偏

- 初次执行曾把“第二 Runtime Host=0”误解为“外置 Host=0”，正常停止唯一 Host 后，binding 从
  rev6/epoch3 ready 自然推进到 rev7/epoch4 disabled/fenced/desired enabled；attempt仍为0，未写
  definition 或业务状态。
- 纯 HTTP 已独立证明 Cron=false、snapshot worker=false、进程内 Host=false。关闭 18181 后，只允许
  以同一 singleton lock 恢复一个外置 Host，读回新的 exact ready binding 后再重新执行 prepare；
  进程计数必须为1，第二 Host仍为0。后续脚本不得硬编码旧 rev6/epoch3。
