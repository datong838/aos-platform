# AX 终态正式退休方案

## 当前权威

AX installation `be884663-0dba-4d9b-aa56-84caaf01147d` / generation
`a14c911b-6796-4d22-a3b0-1817cf502de9` 仍为 active，Binding rev6/epoch3 enabled/ready/unfenced，3/3
resources live，九路 extension rev123/group150。snapshot worker 已停止，18181 已释放；唯一 recoverable Store
attempt `e5b99486-ecf6-460e-b2d3-de40e372d7c9` 是 rev61
`failed/RECOVERABLE_INGRESS_DEADLINE_EXCEEDED/IngressJournalConflict`，definition rev79 disabled。

12 Runs 仍 running、12 Dataset Receipt 保留，Store Receipt、`ecom_link`、outbox、projection pending 和 canary
均为 0。本波仅执行正式 Runtime disable Owner，不改 snapshot Run，不产生新 attempt。

## 文件级清单与顺序

1. 新增 `scripts/a0v_ax_terminal_retirement.py`：只注入 AX exact 身份、lock、唯一 failed attempt、
   definition rev79、active rev123/group150 与预期 detached rev125/group152；复用已验证 AQ 正式
   `preflight → request-disable → process-disable → audit` 路径，不改共享 Owner。
2. 新增专项测试，固定上述常量、单次 delivery、`resendDisable=false`、零 Store 边界与禁止
   `run_definition`。
3. 串行执行四步：preflight 必须先精确读回边界；request 只接受 binding rev6/etag5；process 只允许既有
   Host 已自然完成或原 RuntimeDisableConsumer 领取同一 operation；audit 固定正式终态。
4. verification 落盘并精确提交后，才允许从 exact detach Receipt 规划 AY direct successor。

## 完成与停止条件

- 任一 attempt/definition/route/resource/hash 漂移立即停止；未知 Receipt 只读对账，不换幂等键。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、3/3 resources released、九路 legacy
  rev125/group152、fence+detach 两张 Receipt、definition rev79 disabled、唯一 failed attempt 与零
  Store/ecom/projection/canary。
- 不读取商城源数据，不 push，不改其他分支；230 L0 继续挂起。
