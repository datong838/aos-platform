# AZ 保存快照恢复与 1800 秒自然执行方案

## 上位权威与当前边界

AZ installation `40eee6d9-fb03-4657-a83e-aeb38ec4aeeb`、generation
`7b6befaa-2f92-4e62-85f9-0ca060ec4b90` 已完成九路切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev126/group153；configuration rev1 引用 current runtimePolicy rev9。
definition rev79 disabled，AZ attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、runtime pending 与
canary 均为零。本波只转移冻结输入并允许自然 worker 领取，不读取商城源数据，不调用 `run_definition`，不重发此前
Store 幂等键。

## 文件级清单

1. `scripts/a0v_az_saved_snapshot_recovery.py`：从 exact definition rev79/AX disabled 与 recovery rev25 转移
   冻结组，生成 definition rev80/AZ disabled、recovery rev26 与 definition rev81 enabled；全部结果
   `sourceReads=0`。
2. `scripts/a0v_az_attempt_guard.py` 与专项测试：只读固定唯一自然 attempt、request hash、definition/recovery、
   十二 Run、Store/relationship/projection 边界；running/succeeded/failed/abandoned 之外全部 fail-closed。
3. `scripts/a0v_snapshot_product_api.py` 的 exact deployment lease 收窄到
   `A0V-AZ-SNAPSHOT-WORKER-20260919`，使用 AZ 私有 worker 状态；不放宽 owner/status/expiry、安全 flags 或
   independent-worker 约束。
4. verification 固定纯 HTTP flags、第二 Runtime Host=0、transfer/renew Receipt、唯一自然 attempt 与正式终态。

## 串行步骤

1. 保留当前唯一前台 Runtime Host；证明不存在第二 Host。在 definition rev79 disabled、AZ attempt=0 下启动纯 HTTP
   18181，读回 Cron=false、snapshot worker=false、进程内 Runtime Host=false。
2. 执行 prepare、schedule-ingest、controls；十二 schedule 必须 disabled，AZ attempt 仍为 0。
3. 关闭纯 HTTP 18181并确认端口释放；执行 transfer、renew、enable，要求 definition rev80 AZ disabled、
   recovery rev26、definition rev81 enabled，`sourceReads=0`。
4. 创建 exact deployment lease 后启动唯一自然 snapshot worker；禁止手工 `run_definition`。
5. 观察唯一 AZ attempt 至正式 succeeded/failed/abandoned，固定执行预算 1800 秒；持续核对 heartbeat/Lease、
   十二 Run、Dataset Receipt、Store/link/projection、资源与 canary。
6. succeeded 后只读 inspect 并正式 disable；若 terminal 为
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`/`IngressJournalConflict` 且十二 Run 仍 running、Store/link/projection
   全零，只允许 `pause-terminal` 将 definition rev81 推进为 rev82 disabled，再走退休+direct successor；300 秒
   失败不得在 AZ 内重发。

## 停止条件

- 纯 HTTP 阶段出现 attempt、任一 worker flag 非 false、Runtime Host 数不等于 1或存在第二 Host，立即停止。
- revision、identity、Receipt/hash 漂移，或十二 Run/Dataset Receipt 数量变化，立即冻结只读核账。
- 自然 worker 只允许产生唯一 attempt；未知结果、非零 canary、第二 attempt 均停止，不换 key 重发。
- 不读商城源数据、不 push、不改其他分支；230 L0 继续挂起。
