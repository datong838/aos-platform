# AT 保存快照恢复与纯 HTTP 隔离方案

## 上位权威与事故约束

AT installation `631e6d01-a5bb-4865-95eb-07d5665ed957`、generation
`63ea2c87-f185-4b02-b792-1e3073db4a1b` 已完成九路切换和 12 次新增续租，definition 仍为 rev70 disabled，
AT attempt=0。AS 曾因临时 18181 profile 同时启动 snapshot worker，在 definition enabled 后领取 attempt，随后服务关闭导致
`RECOVERABLE_INGRESS_CANCELLED`。本波必须把“HTTP 配置”和“自然 worker 执行”分开，任何未知结果不重发。

## 文件级清单

1. `scripts/a0v_controlled_api.py`：补充显式 `AOS_SNAPSHOT_GROUP_WORKER_ENABLED=false`；保留 QYH Cron false、
   Runtime Host 关闭、迁移关闭和当前 Product signed root，不改变 API 合同。
2. `services/aos-api/tests/test_a0v_controlled_api.py`：锁定纯 HTTP profile 的两类 worker 均关闭。
3. `scripts/a0v_at_saved_snapshot_recovery.py`：从 exact definition rev70/AS disabled 和 recovery rev22 转移冻结组；
   生成 rev71/AT disabled、recovery rev23 与 definition rev72 enabled，全部 `sourceReads=0`，不含失败重发路径。
4. `services/aos-api/tests/extension_runtime/test_a0v_at_saved_snapshot_recovery.py`：固定 AT/AS 身份、revision、幂等键、
   action 集合和禁止 `run_definition`。
5. `scripts/a0v_at_attempt_guard.py` 与对应专项测试：固定唯一自然 attempt、request hash、definition/recovery、
   十二 Run 和 Store/relationship/projection 边界，只读分类 running/succeeded/failed，未知边界不授权重发。
6. `services/aos-api/aos_api/pipeline_snapshot_schedule_worker.py`、
   `services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py` 与对应专项测试：若真实 1168 条关系处理仍在
   300 秒硬截止前保持 heartbeat/Lease 健康，却被 `_check_active` 终止，则把保存输入恢复的执行预算扩为 1800 秒，
   同时保留 heartbeat 30 秒、Lease 120 秒、取消信号、上限校验和失败终态；不得靠无限等待绕过控制。

## 串行执行

1. 在 definition rev70 disabled、AT attempt=0 下启动 `a0v_product_controlled_api.py` 的纯 HTTP 18181；读回启动 flags，
   必须同时证明 Cron=false、snapshot worker=false、第二 Runtime Host=0。
2. 依次执行 prepare、schedule-ingest、controls；十二 schedule 必须 disabled，配置期间 attempt 仍为 0。
3. 关闭纯 HTTP 18181并确认端口释放；再执行 transfer 和 renew，得到 rev71 disabled、recovery rev23、definition rev72 enabled。
4. 只读确认 authority 后启动既有自然 worker profile并保持进程存活；禁止手工 `run_definition`。
5. 观察唯一 AT attempt：heartbeat/lease、十二 Run、Dataset Receipt、relationship/link command、Store Receipt、
   `ecom_link`、projection pending、资源与 canary；未知提交边界不重发。
6. 若 attempt 因 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 终结，并同时满足十二 Run 仍 running、Store Receipt=0、
   `ecom_link`=0、projection pending=0，则认定为 Store 前的安全性能边界。先让自然 attempt 正式终结，再停用并退休
   AT；完成 1800 秒有界预算修改、自测和服务重载后，才能通过 direct successor 重新授权，旧 generation 不再执行。

## 退出和停止条件

- 纯 HTTP 阶段不得出现 execution attempt；出现即停止并冻结边界。
- transfer 只接受 rev70 AS disabled，结果必须 rev71 AT disabled；renew 只接受 recovery rev22，结果必须 recovery rev23
  和 definition rev72 enabled。
- 自然 worker 启动后不得为等待而停止；直到 attempt succeeded/failed 的正式终态。succeeded 后执行 inspect/disable；
  failed 时先冻结未知提交边界，再走正式退休/direct successor 路径。
- 300 秒失败不得在 AT 内手工重发；自然 worker 自动领取的同 generation 后继 attempt 仍按同一 guard 观察至终态，
  然后关闭 definition。扩容后的 1800 秒仍是固定上限，超限继续 fail-closed。
- 不读取商城源数据、不 push、230 L0 继续挂起，`dev-org/dev-project` 仅作零 canary。
