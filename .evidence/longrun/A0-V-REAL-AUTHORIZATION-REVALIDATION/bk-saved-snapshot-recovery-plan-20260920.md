# BK 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BK installation `8c78f903-ebd8-4589-97a0-afad76e209e0` / generation
`9ea4ba9d-1ef8-45a6-9060-1e4f37c87038` 已完成切换与12次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev159/group186；definition rev112 disabled，BK attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bk_saved_snapshot_recovery.py`：从 definition rev112/BJ disabled 与 recovery rev36 转移
   冻结组，生成 definition rev113/BK disabled、recovery rev37 与 definition rev114 enabled，`sourceReads=0`。
2. 自然 attempt 产生后新增 BK exact guard；监督器固定 identity、数据库 accepted_at、50秒只读间隔与1800秒预算。
3. snapshot launcher exact lease 收窄到 `A0V-BK-SNAPSHOT-WORKER-20260920`，使用 BK 私有状态。

## 串行步骤与停止条件

1. definition rev112 disabled、BK attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；关闭纯 HTTP并确认端口释放；transfer→rev113 disabled，
   renew→recovery rev37/definition rev114 enabled，enable读回 `sourceReads=0`。
3. exact lease 后由同一 supervisor 启动唯一自然 worker；按50秒只读间隔持续采样，terminal 或1800秒预算
   先到即停止 exact worker。
4. 正式终态与零副作用边界确认后 pause-terminal→definition rev115 disabled；禁止第二 attempt或手工重发。
5. 任一 Host、revision、identity、Receipt/hash、十二 Run/Receipt 漂移立即停止；未知结果只读对账。
6. 若 SIGTERM 后180秒未退出，先失败关闭；仅在 exact attempt 正式 terminal、attemptCount=1、零副作用且
   PID/进程组仍精确匹配时，才允许升级一次 SIGKILL。不得重启 worker或重发 attempt。

## 2026-09-20 重启后现场补充

用户在唯一 attempt 运行期间明确要求暂停并重启。监督器仅向本波精确 worker 进程组发送停止信号，未触碰
独立 Runtime Host；数据库随后把该唯一 attempt 正式终结为 `failed / RECOVERABLE_INGRESS_CANCELLED /
IngressJournalConflict`。恢复后必须把这一精确组合按失败冻结边界处理：仅当 attemptCount=1、attempt ID、
request hash、definition rev114、recovery rev37、九路 rev159/group186、十二 Run/Receipt 与零副作用边界全部
一致时，guard 才可映射到既有严格失败闭包。任何字段漂移继续 fail-closed；不得恢复 worker、产生第二
attempt 或调用 `run_definition`。

不读商城源数据、不 push、不改其他分支；230 L0 继续挂起。
