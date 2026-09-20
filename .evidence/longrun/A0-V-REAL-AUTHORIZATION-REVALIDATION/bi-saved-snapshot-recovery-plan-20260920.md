# BI 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BI installation `8ca245a1-8420-4590-b9e4-f92256fc22ce` / generation
`6f527122-a4a5-4056-a4e6-ca888f4b64d7` 已完成切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev153/group180；definition rev106 disabled，BI attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bi_saved_snapshot_recovery.py`：从 definition rev106/BH disabled 与 recovery rev34 转移
   冻结组，生成 definition rev107/BI disabled、recovery rev35 与 definition rev108 enabled，`sourceReads=0`。
2. `scripts/a0v_bi_attempt_guard.py` 在自然 attempt 产生后固定 identity、request hash、definition/recovery、
   十二 Run 与 Store/link/projection 边界。
3. `scripts/a0v_bi_terminal_supervisor.py` 以数据库 `accepted_at` 为不可重置起点，2 秒只读监督 terminal 或
   1800 秒预算；持有 exact worker PID/进程组，停止时单次 SIGTERM 并等待最多180秒排空。
4. snapshot launcher exact lease 收窄到 `A0V-BI-SNAPSHOT-WORKER-20260920`，使用 BI 私有状态。

## 串行步骤

1. definition rev106 disabled、BI attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；十二 schedule disabled，BI attempt仍为0。
3. 关闭纯 HTTP并确认端口释放；transfer→definition rev107 disabled，renew→recovery rev35/definition rev108
   enabled，enable读回 `sourceReads=0`。
4. 创建 exact lease 后，由同一 supervisor 启动唯一自然 worker；禁止手工 `run_definition`。
5. terminal 先到则立即停止并排空 worker；预算先到则先停 worker，保持 rev108 enabled 等待同一 attempt
   正式收敛，不允许第二 attempt。
6. succeeded 严格闭环后 disable；若 deadline/conflict 或 lease-expired 且零副作用边界不变，则
   pause-terminal→definition rev109 disabled，再走退休+direct successor。

## 停止条件

- 任一 worker flag、Host 数、revision、identity、Receipt/hash 或十二 Run/Receipt 漂移，立即停止。
- 自然 worker 只允许一个 attempt；第二 attempt、未知结果、非零 canary 均冻结。
- supervisor 未证明 exact worker 已停止，不得等待终态或继续下一步。
- 不读商城源数据、不 push、不改其他分支；230 L0 继续挂起。
