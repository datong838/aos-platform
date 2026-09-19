# AW 保存快照恢复与 1800 秒自然执行方案

## 上位权威与当前边界

AW installation `f94b9425-9bc4-4369-8ae3-138c50c9ab81`、generation
`a92f7bb2-3d90-4d88-9632-5fc9a70bd650` 已完成九路切换与 12 次新增健康续租。Binding rev6/epoch3
enabled/ready/unfenced，九路 extension rev120/group147；唯一 Runtime Host PID 8154 已读回 1800 秒
recoverable Store 执行上限。definition 仍为 rev76 disabled，AW attempt=0。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、running、
unresolved、runtime pending 与 canary 均为零。本波只转移冻结输入并允许自然 worker 领取，不读取商城源数据，
不调用 `run_definition`，不重发 AV 的 Store 幂等键。

## 文件级清单

1. 对已验证 AV saved-snapshot executor 抽取 installation label/identity、definition/recovery revision、结果标签与
   idempotency key 等波次常量；AV 默认合同和终态 guard 不变。
2. `scripts/a0v_aw_saved_snapshot_recovery.py`：从 exact definition rev76/AV disabled 与 recovery rev24 转移
   冻结组，生成 definition rev77/AW disabled、recovery rev25 与 definition rev78 enabled；所有结果
   `sourceReads=0`。
3. `scripts/a0v_aw_attempt_guard.py` 与专项测试：固定唯一自然 attempt、request hash、definition/recovery、十二 Run、
   Store/relationship/projection 边界，只读分类 running/succeeded/failed/abandoned；未知边界不授权重发。
4. snapshot launcher 的 exact deployment lease/task 仅在原任务 Receipt 需要新 lease 时创建；继续保持 independent
   worker、进程内 Runtime Host=false、Cron=false，禁止复活过期 lease 或放宽 task 绑定。
5. verification 固定纯 HTTP flags、第二 Runtime Host=0、transfer/renew Receipt、唯一自然 attempt 的
   heartbeat/lease、正式终态与全部副作用边界。

## 串行步骤

1. 在 definition rev76 disabled、AW attempt=0 下启动纯 HTTP 18181；读回必须同时证明 Cron=false、
   snapshot worker=false、Runtime Host=false，且系统中只有 launchd Runtime Host PID 8154。
2. 依次执行 prepare、schedule-ingest、controls；十二 schedule 必须 disabled，期间 AW attempt 仍为 0。
3. 关闭纯 HTTP 18181并确认端口释放；再执行 transfer、renew、enable，结果必须是 definition rev77 AW disabled、
   recovery rev25、definition rev78 enabled，且 `sourceReads=0`。
4. 只读确认 authority 与 deployment lease 后启动既有自然 snapshot worker 并保持存活；禁止手工
   `run_definition`。
5. 观察唯一 AW attempt 至正式 succeeded/failed/abandoned：持续核对 heartbeat/Lease、十二 Run、Dataset Receipt、
   relationship/link command、Store Receipt、`ecom_link`、projection pending、资源与 canary。
6. succeeded 后只读 inspect 并正式 disable definition；failed 或 1800 秒后因 Lease 失效而正式 abandoned 时，
   先停止 worker 阻止第二 attempt，冻结 exact 终态与提交边界。只有唯一 attempt、十二 Run 仍 running 且
   Store Receipt/`ecom_link`/projection 全零时，才允许 `pause-terminal` 将 definition rev78 原子推进为 rev79
   disabled；随后走正式 retirement 与 direct successor。不得在 AW 内手工补发或创建第二 attempt。

## 停止条件

- 纯 HTTP 阶段出现 attempt、任一 worker flag 非 false、第二 Runtime Host 非 0，立即停止。
- transfer 只接受 rev76 AV disabled，结果必须 rev77 AW disabled；renew 只接受 recovery rev24，结果必须
  recovery rev25 与 definition rev78 enabled。
- 自然 worker 启动后持续观察唯一 attempt 直到正式终结；1800 秒为固定执行预算，不回退到 300 秒。
- 任一未知结果、非零 canary、identity/revision/hash 漂移、十二 Run 或 Dataset Receipt 数量变化，立即冻结并
  只读核账；不得更换幂等键重发。
- 若 terminal 为 `abandoned/ATTEMPT_LEASE_EXPIRED`，该状态只允许冻结和 `pause-terminal`，不构成重发授权。
- 不读取商城源数据、不 push、不改其他分支；230 L0 继续挂起。

## 现场增补：配置治理 authority 到期

纯 HTTP preflight 与 attempt=0 复核通过后，首次 `prepare` 在任何业务写入和结果文件产生前被正式配置门禁
`budget policy is not effective` 拒绝。只读数据库证据确认 current BudgetPolicy rev8 的
`effectiveUntil=2026-09-19T11:48:51.753918Z`，而基础 BudgetRevision rev1 仍有效至 2027 年；不得延长旧行、
绕过检查或把无 Provider 的 snapshot 准备冒充免授权路径。

恢复必须插入以下串行子波：

1. 新建独立私有 journal，使用既有 `text-readiness-v2` 三个公共合成文本探针，每例仅一次 Provider 调用；
   未知/失败保留 submitted intent，不重试，不包含商城或客户输入。
2. 用 `a0v_formal_text_model_renewal.py` 冻结新 budget/runtimePolicy/model/route 候选，经原 head CAS 与 EvalGate
   正式发布；apply 阶段 ProviderCalls=0、businessRuns=0。任何未知提交先只读查回，禁止新 plan 覆盖。
3. 因 AW configuration 当前引用 runtimePolicy rev8，发布 rev9 后必须走既有同 installation/generation
   configuration refresh 正式链：新 configuration → configure/enable → no-effect dispatch refresh；九路继续绑定
   AW exact identity，claim/running/unknown 均为零。禁止直接改 binding/route 或复用旧审批。
4. 重新执行 AW `prepare`；只有新 current exact refs、AW Binding/九路 refresh readback 与 attempt=0 同时成立，
   才恢复原步骤 2–6。

## 现场增补：旧 activation 的 refresh 历史不允许跨 direct successor 续接

BudgetPolicy/RuntimePolicy 已正式续期，AW 同 installation/generation configuration rev2 已经由 configure/enable
落为 Binding rev9/epoch5；全程 ProviderCalls=0、businessRuns=0、AW attempt=0。随后只读复核发现：当前
`extension_dispatch_configuration_refresh_receipt` 的唯一历史属于早期 J activation；数据库 Owner 与不可变触发器
同时要求后续 receipt 继续同一 activation operation、installation、generation。AW 若引用旧 J receipt 会违反 exact
root target，若引用本次 AW resume 又会违反 latest refresh authority。不得绕过触发器、改旧 receipt、直接更新九路，
也不在现场临时扩张主库历史模型。

因此本方案在“配置 refresh readback”门禁处正式停止，原步骤 2–6 不再对 AW 执行。冻结边界为 definition rev76
disabled、AW attempt=0、十二 Run 与 Dataset Receipt 保留、Store/link/projection/canary 全零；AW Binding rev9/epoch5
enabled/ready/unfenced，但九路仍为 AW epoch3 rev120/group147。下一波必须先用既有 disable Owner 正式 fence/detach
AW，再由 direct successor AX 使用 current policy/configuration 创建全新 activation。该停止分支不授权手工
`run_definition`、不授权 Store 重发，也不授权数据库迁移。
