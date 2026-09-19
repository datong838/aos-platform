# AV 保存快照恢复与 1800 秒自然执行方案

## 上位权威与当前边界

AV installation `5f01eda8-ca5f-4892-8510-385704ccddb2`、generation
`17104053-f4c9-47e1-89b0-f3f353076dda` 已完成九路切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev117/group144；唯一 Runtime Host 已读回 1800 秒 recoverable Store
执行上限。definition 仍为 rev73 disabled，AV attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、running、
unresolved、runtime pending 与 canary 均为零。本波只转移冻结输入并允许自然 worker 领取，不读取商城源数据，
不调用 `run_definition`，不重发 AT/AU 的任何 Store 幂等键。

## 文件级清单

1. `scripts/a0v_av_saved_snapshot_recovery.py`：从 exact definition rev73/AT disabled 与 recovery rev23 转移冻结组；
   AU 因健康过期从未接管该 definition，运行时 predecessor 与快照 definition predecessor 必须分别核验。执行器生成
   生成 rev74/AV disabled、recovery rev24 与 definition rev75 enabled；所有结果 `sourceReads=0`。
2. 对应专项测试固定 AV/AU 身份、revision、幂等键、action 集合以及禁止 `run_definition`。
3. `scripts/a0v_av_attempt_guard.py` 与专项测试：固定唯一自然 attempt、request hash、definition/recovery、十二 Run、
   Store/relationship/projection 边界，只读分类 running/succeeded/failed；未知边界不授权重发。
4. verification：记录纯 HTTP flags、第二 Runtime Host=0、transfer/renew Receipt、自然 worker 唯一 attempt 的
   heartbeat/lease、正式终态与所有副作用边界。
5. `pipeline_snapshot_schedule_definition.py` 与真实 PG 专项测试：现场 preflight 发现 definition 仍属于 AT，而 AV 是
   AT→AU→AV 的两跳正式后继。Owner 必须在同一事务内逐节点校验有限、无环、exact `currentInstallationRef` 链；AT 与
   每个中间节点都必须 active 但 runtime disabled/fenced、正式 detached、3/3 resources released，AV 必须 ready 且
   九路当前。原有一跳合同保持不变，缺节点、环、未退休中间节点或跨租户均拒绝，禁止以直接改表绕过。
6. `scripts/a0v_snapshot_product_api.py` 与既有启动器测试：现场首次自然 worker 启动在任何业务执行前
   被过期的 `SC4-5L6Y6C-SPLIT-WORKER-20260916` 部署 lease 拒绝，attempt 仍为 0。该任务的正式
   Delivery Receipt 明确要求“重启须新部署 lease”；因此创建本波窄范围
   `A0V-AV-SNAPSHOT-WORKER-20260919` lease，启动器只接受该 exact task/owner/ACTIVE/未过期四项合同。
   禁止复活旧任务或放宽为任意 m1 lease；仍保持 independent worker、进程内 Runtime Host=false。

## 串行步骤

1. 在 definition rev73 disabled、AV attempt=0 下启动纯 HTTP 18181；启动读回必须同时证明 Cron=false、
   snapshot worker=false、Runtime Host=false，且系统中仅有 launchd 的唯一 Runtime Host。
2. 依次执行 prepare、schedule-ingest、controls；十二 schedule 必须 disabled，配置期间 AV attempt 仍为 0。
3. 关闭纯 HTTP 18181并确认端口释放；再执行 transfer、renew、enable，结果必须是 definition rev74 AV disabled、
   recovery rev24、definition rev75 enabled，且 `sourceReads=0`。
4. 只读确认 authority，创建本波 exact 部署 lease 并通过启动器门禁后，启动既有自然 snapshot worker
   profile 并保持存活；禁止手工 `run_definition`。
5. 观察唯一 AV attempt 至正式 succeeded/failed：持续核对 heartbeat/Lease、十二 Run、Dataset Receipt、
   relationship/link command、Store Receipt、`ecom_link`、projection pending、资源与 canary。
6. succeeded 后只读 inspect 并正式 disable definition；failed 或在 1800 秒后因 Lease 失效而正式
   abandoned 时，先停止 worker 以阻止第二 attempt，冻结 exact 终态与提交边界。只有当唯一 attempt、
   十二 Run 仍 running 且 Store Receipt/`ecom_link`/projection 全零时，才允许 `pause-terminal` 将
   definition rev75 原子推进为 rev76 disabled；然后按正式退休和 direct successor 路径继续。
   不得在 AV 内手工补发或创建第二 attempt。

## 停止条件

- 纯 HTTP 阶段出现 attempt、任一 worker flag 非 false、第二 Runtime Host 非 0，立即停止。
- transfer 只接受 rev73 AT disabled，结果必须 rev74 AV disabled；renew 只接受 recovery rev23，结果必须 recovery
  rev24 与 definition rev75 enabled。
- 自然 worker 启动后不因等待而停止，直到唯一 attempt 正式终结；1800 秒仍是固定上限，超限 fail-closed。
- 若 attempt 在 1800 秒后终结为 `abandoned/ATTEMPT_LEASE_EXPIRED`，该状态只允许冻结和
  `pause-terminal`，不具有任何自然 successor 或重发授权。
- 任一未知结果、非零 canary、identity/revision/hash 漂移、十二 Run 或 Dataset Receipt 数量变化，立即冻结并只读核账。
- 若 transfer 返回 `exact active replacement lineage required`，且 definition head/Receipt 仍未变化，只能先补充上述
  transitive exact-lineage Owner 合同与真实 PG RED→GREEN；不得换幂等键或伪造 AV 为 AT 的直接子代。
- 不读取商城源数据、不 push、不改其他分支；230 L0 继续挂起。
