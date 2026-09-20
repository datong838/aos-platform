# BL 保存快照恢复与严格 1800 秒单 attempt 方案

## 当前权威

BL installation `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation
`116d12fc-93bc-4071-a973-fdc6830ea8b1` 已完成切换与12次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev162/group189；definition rev115 disabled，BL attempt=0。

十二 Run仍 running、十二 Dataset Receipt保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_bl_saved_snapshot_recovery.py`：从 definition rev115/BK disabled与 recovery rev37转移
   冻结组，生成 definition rev116/BL disabled、recovery rev38与 definition rev117 enabled，`sourceReads=0`。
2. 自然 attempt产生后新增 BL exact guard；监督器固定 identity、数据库 accepted_at、50秒只读间隔与1800秒预算。
3. snapshot launcher exact lease收窄到 `A0V-BL-SNAPSHOT-WORKER-20260920`，使用 BL私有状态。

## 串行步骤与停止条件

1. definition rev115 disabled、BL attempt=0下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；关闭纯 HTTP并确认端口释放；transfer→rev116 disabled，
   renew→recovery rev38/definition rev117 enabled，enable读回 `sourceReads=0`。
3. exact lease后由同一 supervisor启动唯一自然 worker；按50秒只读间隔持续采样，terminal或1800秒预算
   先到即停止 exact worker。
4. 正式终态与零副作用边界确认后 pause-terminal→definition rev118 disabled；禁止第二 attempt或手工重发。
5. 任一 Host、revision、identity、Receipt/hash、十二 Run/Receipt漂移立即停止；未知结果只读对账。
6. 若 SIGTERM后180秒未退出，先失败关闭；仅在 exact attempt正式 terminal、attemptCount=1、零副作用且
   PID/进程组仍精确匹配时，才允许升级一次 SIGKILL。不得重启 worker或重发 attempt。

## 观察中运行凭据丢失补充边界

07:39Z 后外部 Runtime Host 因其受保护 credential reference 文件被移除而 `HOST_RUNTIME_FAILED`，
自然 worker 随后以 `RUNTIMEERROR` 停止；监督器因同一已签名运行目录缺失而 fail-closed 退出。该事故
不是业务调用终态，也不授权恢复文件、重启 Host/worker 或重发 attempt。

仅当数据库 accepted_at 已满原 1800 秒预算、Lease 已明确过期、Host/worker/supervisor 三类进程均为零、
唯一 BL attempt 仍为原 request hash 的 running revision45、十二 Run/Receipt 与 Store/ecom/projection
零事实均未漂移时，允许新增 exact recovery adapter，使用既有 `ExpiredSignedReadAttemptRecovery` Owner
一次性执行 `abandon_expired_reads`。预期只把该 attempt 原子推进为 revision46
`abandoned / ATTEMPT_LEASE_EXPIRED / null`；不得读取商城源、不得创建 attempt、不得执行 definition。
任一条件不符立即 `SAFE_BLOCKED`。

credential reference 丢失同时使常规 `pause-terminal` 组合入口不可构造；在上述 abandoned readback 完成后，
只允许以 runtime role 调用原 `PipelineSnapshotScheduleDefinitionOwner(controls=None)` 的 stop-only
`disable` transition，固定 expected rev117 与幂等键，读回 rev118 disabled。不得构造 source controls。

不读商城源数据、不 push、不改其他分支；230 L0继续挂起。
