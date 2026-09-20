# BH 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BH installation `7b7d4319-e639-48c9-971b-0efbfb9251ef` / generation
`f6023b7c-ca6f-49ac-b9ff-4dcbca62745c` 已完成切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev150/group177；definition rev103 disabled，BH attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bh_saved_snapshot_recovery.py`：从 exact definition rev103/BG disabled 与 recovery rev33 转移
   冻结组，生成 definition rev104/BH disabled、recovery rev34 与 definition rev105 enabled；全部结果
   `sourceReads=0`。
2. `scripts/a0v_bh_attempt_guard.py` 与专项测试：在自然 attempt 产生后固定其 identity、request hash、
   definition/recovery、十二 Run 与 Store/link/projection 边界。
3. `scripts/a0v_bh_terminal_supervisor.py`：以数据库 `accepted_at` 为不可重置起点，2 秒只读监督 terminal 或
   1800 秒预算；同一进程持有 exact worker PID/进程组，停止时单次 SIGTERM 并等待最多180秒完整排空。
4. snapshot launcher exact lease 收窄到 `A0V-BH-SNAPSHOT-WORKER-20260920`，使用 BH 私有状态；变更 launcher
   后必须先由纯 HTTP 路径复核 worker=false，再启动唯一自然 worker。

## 串行步骤

1. definition rev103 disabled、BH attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，并证明外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；十二 schedule disabled，BH attempt仍为0。
3. 关闭纯 HTTP并确认端口释放；transfer→definition rev104 disabled，renew→recovery rev34/definition rev105
   enabled，enable读回 `sourceReads=0`。
4. 创建 exact lease 后，由同一受控 supervisor 启动唯一自然 worker；禁止手工 `run_definition`。取得唯一
   attempt 与 worker PID 后写入 guard identity，并以数据库 `accepted_at` 启动不可重置的1800秒监督。
5. 若 terminal 先到，supervisor 立即停止并排空 worker后完整核账；若预算先到，supervisor 先停止并排空
   worker，再保持 definition rev105 enabled、等待唯一 Runtime Host 仅将同一 attempt 正式收敛；不允许第二 attempt。
6. succeeded严格闭环后disable；若唯一attempt为deadline/conflict或lease-expired且十二Run running、Store/link/
   projection全零，则 pause-terminal→definition rev106 disabled，再走退休+direct successor。

## 停止条件

- 任一 worker flag、Host 数、revision、identity、Receipt/hash 或十二 Run/Receipt 漂移，立即停止。
- 自然 worker只允许一个attempt；第二attempt、未知结果、非零canary均冻结，不执行 pause。
- supervisor 未能证明 exact worker 已停止，不得继续等待终态或执行任何下一步。
- 不读商城源数据、不push、不改其他分支；230 L0继续挂起。
