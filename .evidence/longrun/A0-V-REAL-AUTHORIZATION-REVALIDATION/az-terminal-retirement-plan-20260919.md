# AZ 两终态正式退休方案

## 当前权威

AZ installation `40eee6d9-fb03-4657-a83e-aeb38ec4aeeb` / generation
`7b6befaa-2f92-4e62-85f9-0ca060ec4b90` 仍为 active；Binding rev6/epoch3 enabled/ready/unfenced，
三资源 live，九路 extension rev126/group153。definition rev82 disabled，snapshot worker 已停止，18181 已释放。

固定 attempt 历史为：首个 revision 61
`failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`；第二个 revision 4
`abandoned / ATTEMPT_LEASE_EXPIRED`。十二 Run 仍 running、十二 Dataset Receipt 保留，Store Receipt、
`ecom_link`、outbox、projection pending 与 canary 均为 0。

## 文件级清单与顺序

1. 新增 `scripts/a0v_az_terminal_retirement.py`：只注入 AZ exact 身份、lock、两次 terminal attempt、
   definition rev82、active rev126/group153 与预期 detached rev128/group155；复用正式 AQ
   `preflight → request-disable → process-disable → audit` Owner 路径。
2. 新增专项测试，固定上述常量、单次 delivery、`resendDisable=false`、零 Store 边界和禁止
   `run_definition`。
3. 串行执行四步；request 只接受现有 Binding rev6/etag5，process 只允许唯一 Runtime Host 自然领取
   同一 disable operation，或在明确未领取时由原 RuntimeDisableConsumer 领取一次。
4. verification 落盘并精确提交后，才允许从 exact detach Receipt 规划 BA direct successor。

## 完成与停止条件

- attempt/definition/route/resource/hash 任一漂移立即停止；未知 Receipt 只读对账，不换幂等键。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy
  rev128/group155、fence+detach 两张 Receipt、definition rev82 disabled、两次 exact terminal attempt 与
  Store/ecom/projection/canary 全零。
- 不启动 snapshot worker，不创建第三 attempt，不读取商城源数据，不 push，不改其他分支；230 L0 继续挂起。
