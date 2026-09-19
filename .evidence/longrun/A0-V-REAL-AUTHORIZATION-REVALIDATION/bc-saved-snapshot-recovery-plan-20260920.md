# BC 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BC installation `3b895c30-34ca-4710-b978-02645d49c83a` / generation
`31776dcd-e28f-4b6d-ae45-75fb0ab5a505` 已完成切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev135/group162；definition rev88 disabled，BC attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bc_saved_snapshot_recovery.py`：从 exact definition rev88/BB disabled 与 recovery rev28 转移
   冻结组，生成 definition rev89/BC disabled、recovery rev29 与 definition rev90 enabled；全部结果
   `sourceReads=0`。
2. `scripts/a0v_bc_attempt_guard.py` 与专项测试：固定唯一自然 attempt、request hash、definition/recovery、十二
   Run 与 Store/link/projection 边界。
3. snapshot launcher exact lease 收窄到 `A0V-BC-SNAPSHOT-WORKER-20260920`，使用 BC 私有状态。
4. worker 启动并取得 exact PID 后立刻启动单一监督链：2 秒只读监视；首个 terminal 或从 attempt accepted 起
   1800 秒预算到点，两者任一先发生都立即停止 exact worker。监督不得重启计时。

## 串行步骤

1. definition rev88 disabled、BC attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，并证明外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；十二 schedule disabled，BC attempt仍为0。
3. 关闭纯 HTTP并确认端口释放；transfer→definition rev89 disabled，renew→recovery rev29/definition rev90
   enabled，enable读回 `sourceReads=0`。
4. 创建 exact lease 后启动唯一自然 worker；禁止手工 `run_definition`。取得唯一 attempt 与 worker PID 后启动
   不可重置的 1800 秒监督。
5. 若 terminal 先到，立即停worker并完整核账；若预算先到，立即停worker，保持 definition rev90 enabled 但无
   worker，等待唯一 Runtime Host 仅将同一 attempt 正式收敛，不允许第二 attempt。
6. succeeded严格闭环后disable；若唯一attempt为deadline/conflict或lease-expired且十二Run running、Store/link/
   projection全零，则 pause-terminal→definition rev91 disabled，再走退休+direct successor。

## 停止条件

- 任一 worker flag、Host 数、revision、identity、Receipt/hash 或十二 Run/Receipt 漂移，立即停止。
- 自然 worker只允许一个attempt；第二attempt、未知结果、非零canary均冻结，不执行 pause。
- 不读商城源数据、不push、不改其他分支；230 L0继续挂起。
