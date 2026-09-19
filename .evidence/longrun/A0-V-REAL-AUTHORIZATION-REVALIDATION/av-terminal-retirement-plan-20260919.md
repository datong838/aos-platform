# AV 终态正式退休方案

## 当前权威

AV installation `5f01eda8-ca5f-4892-8510-385704ccddb2` / generation
`17104053-f4c9-47e1-89b0-f3f353076dda` 仍为 active，Binding rev6/epoch3 enabled/ready/unfenced，3/3
resources live，九路 extension rev117/group144。snapshot worker 已停止，18181 已释放；唯一
recoverable Store attempt `42717b1a-1d3b-442d-9b18-683593e4bbbf` 是 rev61
`abandoned/ATTEMPT_LEASE_EXPIRED`，definition rev76 disabled。

12 Runs 仍 running、12 Dataset Receipt 保留，Store Receipt、`ecom_link`、outbox、projection pending 和
canary 均为 0。本波仅执行正式 Runtime disable Owner，不改 snapshot Run，不产生新 attempt。

## 文件级清单与顺序

1. 将已验证的 AQ retirement 执行器中的 definition/route revision 字面量提取为模块常量；
   AQ 默认值、行为和专项测试保持不变，不改 disable Owner 逻辑。
2. 新增 `scripts/a0v_av_terminal_retirement.py`：只注入 AV exact 身份、lock、唯一 abandoned attempt、
   definition rev76、active rev117/group144 与预期 detached rev119/group146；复用正式
   `preflight → request-disable → process-disable → audit` 路径。
3. 专项测试固定上述常量、单次 delivery、`resendDisable=false`、零 Store 边界与禁止
   `run_definition`。
4. 执行四步后落盘 verification，只提交本波文件；退休 Receipt 落盘后才允许下一波
   AW direct successor。

## 完成与停止条件

- preflight 必须精确读回上述 AV 边界；任一 attempt/definition/route/resource/hash 漂移即停止。
- request 只允许 expected binding rev6 和 installation etag5；未知 Receipt 先对账，不换幂等键。
- process 只允许 Host 自然已完成或原 RuntimeDisableConsumer 领取同一 operation，禁止第二次
  disable delivery。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、3/3 resources released、九路 legacy
  rev119/group146、fence+detach 两张 Receipt、definition rev76 disabled、唯一 abandoned attempt 与零
  Store/ecom/projection/canary。
- 不读取商城源数据，不 push，不改其他分支；230 L0 继续挂起。
