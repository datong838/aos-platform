# BJ 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BJ installation `2c3972b1-67c1-400d-aa63-b90de369f5de` / generation
`8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b` 已完成切换与12次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev156/group183；definition rev109 disabled，BJ attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bj_saved_snapshot_recovery.py`：从 definition rev109/BI disabled 与 recovery rev35 转移
   冻结组，生成 definition rev110/BJ disabled、recovery rev36 与 definition rev111 enabled，`sourceReads=0`。
2. 自然 attempt 产生后新增 BJ exact guard；监督器固定 identity、数据库 accepted_at 与1800秒预算。
3. snapshot launcher exact lease 收窄到 `A0V-BJ-SNAPSHOT-WORKER-20260920`，使用 BJ 私有状态。

## 串行步骤与停止条件

1. definition rev109 disabled、BJ attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；关闭纯 HTTP并确认端口释放；transfer→rev110 disabled，
   renew→recovery rev36/definition rev111 enabled，enable读回 `sourceReads=0`。
3. exact lease 后由同一 supervisor 启动唯一自然 worker；按50秒只读间隔持续采样，terminal 或1800秒预算
   先到即停止 exact worker。
4. 正式终态与零副作用边界确认后 pause-terminal→definition rev112 disabled；禁止第二 attempt或手工重发。
5. 任一 Host、revision、identity、Receipt/hash、十二 Run/Receipt 漂移立即停止；未知结果只读对账。

## 有界排空异常恢复

若 exact worker 已收到一次 SIGTERM、18181 已释放，但 180 秒内进程未退出，则 supervisor 必须先失败关闭；
只有在 exact attempt 已读回正式 terminal、attemptCount=1、十二 Run/Receipt 与零副作用边界均未漂移，且残留
PID/进程组仍精确等于本次 worker 时，才允许向该精确进程组升级一次 SIGKILL 并等待退出。不得重启 worker、不得
重发 attempt、不得手工执行 definition；恢复过程与首次排空异常必须写入 verification。

不读商城源数据、不 push、不改其他分支；230 L0 继续挂起。
