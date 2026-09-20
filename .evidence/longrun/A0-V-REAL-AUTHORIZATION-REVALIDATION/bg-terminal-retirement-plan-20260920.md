# BG 单终态正式退休方案

## 当前权威

BG installation `c52ab6db-176e-4378-ac88-2ee1bfc58487` / generation
`477c3f92-06f0-4dae-9445-ce6d09c3f462` 仍为 active；Binding rev6/epoch3 enabled/ready/unfenced，
三资源 live，九路 extension rev147/group174。definition rev103 disabled，snapshot worker 已停止，18181 已释放。

固定唯一 attempt `a42bc506-7e3c-48cd-bde7-1eb0b1adc93f` 为 revision61
`abandoned / ATTEMPT_LEASE_EXPIRED / null`。十二 Run 仍 running、十二 Dataset Receipt 保留，Store Receipt、
`ecom_link`、outbox、projection pending 与 canary 均为0。本波只接受该 exact 边界。

## 文件级清单与顺序

1. 新增 `scripts/a0v_bg_terminal_retirement.py`：只注入 BG exact 身份、lock、单 terminal attempt、
   definition rev103、active rev147/group174 与预期 detached rev149/group176；复用正式 AQ
   `preflight → request-disable → process-disable → audit` Owner 路径。
2. 新增专项测试，固定上述常量、唯一 disable delivery、`resendDisable=false`、零 Store 边界和禁止
   `run_definition`。
3. 串行执行四步；request 只接受现有 Binding rev6/etag5，process 只允许唯一 Runtime Host 自然领取
   同一 disable operation，或在明确未领取时由原 RuntimeDisableConsumer 领取一次。
4. verification 落盘并精确提交后，才允许从 exact detach Receipt 规划 BH direct successor。

## 完成与停止条件

- attempt/definition/route/resource/hash 任一漂移立即停止；未知 Receipt 只读对账，不换幂等键。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy
  rev149/group176、fence+detach 两张 Receipt、definition rev103 disabled、exact 单 terminal history与
  Store/ecom/projection/canary 全零。
- 不启动 snapshot worker，不创建第二 attempt，不读取商城源数据，不 push，不改其他分支；230 L0 继续挂起。
