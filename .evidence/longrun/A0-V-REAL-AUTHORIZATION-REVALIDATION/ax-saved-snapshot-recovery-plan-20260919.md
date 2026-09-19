# AX 保存快照恢复与 1800 秒自然执行方案

## 上位权威与当前边界

AX installation `be884663-0dba-4d9b-aa56-84caaf01147d`、generation
`a14c911b-6796-4d22-a3b0-1817cf502de9` 已完成九路切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev123/group150；configuration rev1 明确引用 current runtimePolicy rev9。
definition 仍为 rev76 disabled，AX attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、running、
unresolved、runtime pending 与 canary 均为零。本波只转移冻结输入并允许自然 worker 领取，不读取商城源数据，
不调用 `run_definition`，不重发此前 Store 幂等键。

## 文件级清单

1. `scripts/a0v_ax_saved_snapshot_recovery.py`：复用已验证执行器，从 exact definition rev76/AV disabled 与
   recovery rev24 转移冻结组，生成 definition rev77/AX disabled、recovery rev25 与 definition rev78 enabled；
   所有准备/转移结果 `sourceReads=0`。
2. `scripts/a0v_ax_attempt_guard.py` 与专项测试：固定唯一自然 attempt、request hash、definition/recovery、十二
   Run、Store/relationship/projection 边界，只读分类 running/succeeded/failed/abandoned；未知边界不授权重发。
   AX wrapper 必须把复用执行器的 terminal guard 与允许的 failed/abandoned 冻结结果显式接线到本 guard，禁止沿用
   AV 身份或仅接受 AV abandoned 结果。
3. `scripts/a0v_snapshot_product_api.py` 与既有启动器测试：将上波 AV exact deployment lease 门禁收窄迁移为
   `A0V-AX-SNAPSHOT-WORKER-20260919`，并使用 AX 私有状态目录；不放宽 owner/status/expiry 校验，不改变
   independent worker、进程内 Runtime Host=false、Cron=false 等既有安全 flags。启动前创建本波窄范围部署 lease，
   禁止复活或复用 AV lease。
4. verification 固定纯 HTTP flags、第二 Runtime Host=0、transfer/renew Receipt、唯一自然 attempt 的
   heartbeat/lease、正式终态与全部副作用边界。

## 串行步骤

1. 在 definition rev76 disabled、AX attempt=0 下启动纯 HTTP 18181；读回同时证明 Cron=false、snapshot
   worker=false、进程内 Runtime Host=false，且第二 Runtime Host=0。
2. 依次执行 prepare、schedule-ingest、controls；十二 schedule 必须 disabled，期间 AX attempt 仍为 0。
3. 关闭纯 HTTP 18181并确认端口释放；再执行 transfer、renew、enable，结果必须为 definition rev77 AX
   disabled、recovery rev25、definition rev78 enabled，且 `sourceReads=0`。
4. 只读确认 authority 与 deployment lease 后启动既有自然 snapshot worker并保持存活；禁止手工
   `run_definition`。
5. 观察唯一 AX attempt 至正式 succeeded/failed/abandoned，固定执行预算 1800 秒；持续核对 heartbeat/Lease、
   十二 Run、Dataset Receipt、Store/link/projection、资源与 canary。
6. succeeded 后只读 inspect 并正式 disable definition；若 terminal 为
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 或 Lease 失效终结，且十二 Run 仍 running、Store/link/projection 全零，
   只允许 `pause-terminal` 将 definition rev78 推进为 rev79 disabled，再走 retirement + direct successor；
   300 秒失败不在 AX 内手工重发。

## 停止条件

- 纯 HTTP 阶段出现 attempt、任一 worker flag 非 false、第二 Runtime Host 非 0，立即停止。
- transfer/renew/enable revision、identity、hash 任一漂移，或十二 Run/Dataset Receipt 数量变化，立即冻结只读核账。
- 自然 worker 只允许产生唯一 attempt；未知结果、非零 canary、第二 attempt 均停止，不换键重发。
- 不读取商城源数据、不 push、不改其他分支；230 L0 继续挂起。
