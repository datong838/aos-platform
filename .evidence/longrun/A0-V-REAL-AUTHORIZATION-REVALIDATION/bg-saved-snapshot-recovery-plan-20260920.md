# BG 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BG installation `c52ab6db-176e-4378-ac88-2ee1bfc58487` / generation
`477c3f92-06f0-4dae-9445-ce6d09c3f462` 已完成切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev147/group174；definition rev100 disabled，BG attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bg_saved_snapshot_recovery.py`：从 exact definition rev100/BF disabled 与 recovery rev32 转移
   冻结组，生成 definition rev101/BG disabled、recovery rev33 与 definition rev102 enabled；全部结果
   `sourceReads=0`。
2. `scripts/a0v_bg_attempt_guard.py` 与专项测试：在自然 attempt 产生后固定其 identity、request hash、
   definition/recovery、十二 Run 与 Store/link/projection 边界。
3. `scripts/a0v_bg_terminal_supervisor.py`：以数据库 `accepted_at` 为不可重置起点，2 秒只读监督 terminal 或
   1800 秒预算；在同一进程内持有 exact worker PID/进程组，`stopWorker=true` 时先终止 worker 并等待退出，
   再输出最终判定，修复 BF monitor 与停止动作分离造成的第二 attempt 窗口。
4. snapshot launcher exact lease 收窄到 `A0V-BG-SNAPSHOT-WORKER-20260920`，使用 BG 私有状态；变更 launcher
   后必须先由纯 HTTP 路径复核 worker=false，再启动唯一自然 worker。

## 串行步骤

1. definition rev100 disabled、BG attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，并证明外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；十二 schedule disabled，BG attempt仍为0。
3. 关闭纯 HTTP并确认端口释放；transfer→definition rev101 disabled，renew→recovery rev33/definition rev102
   enabled，enable读回 `sourceReads=0`。
4. 创建 exact lease 后，由同一受控 supervisor 启动唯一自然 worker；禁止手工 `run_definition`。取得唯一
   attempt 与 worker PID 后写入 guard identity，并以数据库 `accepted_at` 启动不可重置的 1800 秒监督。
5. 若 terminal 先到，supervisor 立即停止并排空 worker后完整核账；若预算先到，supervisor 先停止并排空
   worker，再保持 definition rev102 enabled、等待唯一 Runtime Host 仅将同一 attempt 正式收敛；不允许第二 attempt。
6. succeeded严格闭环后disable；若唯一attempt为deadline/conflict或lease-expired且十二Run running、Store/link/
   projection全零，则 pause-terminal→definition rev103 disabled，再走退休+direct successor。

## 停止条件

- 任一 worker flag、Host 数、revision、identity、Receipt/hash 或十二 Run/Receipt 漂移，立即停止。
- 自然 worker只允许一个attempt；第二attempt、未知结果、非零canary均冻结，不执行 pause。
- supervisor 未能证明 exact worker 已停止，不得继续等待终态或执行任何下一步。
- 不读商城源数据、不push、不改其他分支；230 L0继续挂起。
