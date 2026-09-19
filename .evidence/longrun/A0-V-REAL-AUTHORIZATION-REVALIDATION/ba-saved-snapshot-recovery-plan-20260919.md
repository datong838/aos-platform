# BA 保存快照恢复与单 attempt 终态方案

## 当前权威

BA installation `9110f69b-bb31-4d17-98e8-6c5ed1d9234f` / generation
`197f5036-656a-4b58-a261-e93e2fffea18` 已完成切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev129/group156；definition rev82 disabled，BA attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending
与 canary 均为零。本波只转移冻结输入，不读取商城源数据，不调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_ba_saved_snapshot_recovery.py`：从 exact definition rev82/AZ disabled 与 recovery rev26 转移
   冻结组，生成 definition rev83/BA disabled、recovery rev27 与 definition rev84 enabled；全部结果
   `sourceReads=0`。
2. `scripts/a0v_ba_attempt_guard.py` 与专项测试：固定唯一自然 attempt、request hash、definition/recovery、十二
   Run 与 Store/link/projection 边界。
3. snapshot launcher exact lease 收窄到 `A0V-BA-SNAPSHOT-WORKER-20260919`，使用 BA 私有状态。
4. 针对 AZ 终态后 20 秒内自动领取第二 attempt 的事实，本波增加 2 秒只读终态监视：第一个 attempt 一旦
   terminal，立即停止 worker 与 18181；若仍产生第二 attempt，按 stop 条件冻结，不执行 pause。

## 串行步骤

1. definition rev82 disabled、BA attempt=0 下启动纯 HTTP 18181；读回 Cron=false、snapshot worker=false、
   进程内 Runtime Host=false，并证明外部 Host恰为1、第二 Host=0。
2. prepare、schedule-ingest、controls；十二 schedule disabled，BA attempt仍为0。
3. 关闭纯 HTTP并确认端口释放；transfer→definition rev83 disabled，renew→recovery rev27/definition rev84
   enabled，enable读回 `sourceReads=0`。
4. 创建 exact lease 后启动唯一自然 worker；禁止手工 `run_definition`。2秒 guard监视唯一 attempt，最长
   1800秒；terminal后优先停worker，再做完整只读核账。
5. succeeded严格闭环后disable；若首个attempt为deadline/conflict且十二Run running、Store/link/
   projection全零，则停worker后pause-terminal→definition rev85 disabled，再走退休+direct successor。

## 停止条件

- 任一 worker flag、Host 数、revision、identity、Receipt/hash 或十二 Run/Receipt 漂移，立即停止。
- 自然 worker只允许一个attempt；第二attempt、未知结果、非零canary均冻结，不换key、不重发。
- 不读商城源数据、不push、不改其他分支；230 L0继续挂起。
