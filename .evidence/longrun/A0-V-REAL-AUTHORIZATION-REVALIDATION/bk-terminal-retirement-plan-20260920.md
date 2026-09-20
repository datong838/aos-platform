# BK 单终态正式退休方案

## 当前权威

BK installation `8c78f903-ebd8-4589-97a0-afad76e209e0` / generation
`9ea4ba9d-1ef8-45a6-9060-1e4f37c87038` 仍为 active；Binding rev6/epoch3 enabled/ready/unfenced，
三资源 live，九路 extension rev159/group186。definition rev115 disabled，snapshot worker 已停止，18181 已释放。

固定唯一 attempt `c0b032b7-30c1-4260-9b67-99e298347dea` 为 revision13
`failed / RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict`。十二 Run 仍 running、十二 Dataset Receipt
保留，Store Receipt、`ecom_link`、outbox、projection pending 与 canary 均为0。本波只接受该 exact 边界。

## 文件级清单与顺序

1. 新增 `scripts/a0v_bk_terminal_retirement.py`：只注入 BK exact 身份、lock、单 terminal attempt、
   definition rev115、active rev159/group186 与预期 detached rev161/group188；复用正式 AQ
   `preflight → request-disable → process-disable → audit` Owner 路径。
2. 新增专项测试，固定上述常量、唯一 disable delivery、`resendDisable=false`、零 Store 边界和禁止
   `run_definition`。
3. 串行执行四步。系统重启后外部 Runtime Host=0；request 只接受现有 Binding rev6/etag5，process 仅在
   operation 明确未领取时由原 `RuntimeDisableConsumer` 领取并完成一次，不启动新 Host、不更换幂等键。
4. verification 落盘并精确提交后，才允许从 exact detach Receipt 规划 BL direct successor。

## 完成与停止条件

- attempt/definition/route/resource/hash 任一漂移立即停止；未知 Receipt 只读对账，不换幂等键。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy
  rev161/group188、fence+detach 两张 Receipt、definition rev115 disabled、exact 单 terminal history与
  Store/ecom/projection/canary 全零。
- 不启动 snapshot worker，不创建第二 attempt，不读取商城源数据，不 push，不改其他分支；230 L0继续挂起。

## process 后资源释放恢复门禁

现场 `process-disable` 已将唯一 operation 正式提交为 succeeded、Binding rev8/epoch4 fenced/disabled、九路
legacy rev161/group188，并生成 fence/detach 两张 Receipt；但因系统重启后 Runtime Host=0，三项资源仍为
`pending / observed_release=false`，最终 snapshot 因此 fail-closed，且未写 process result。禁止重跑
`process-disable`。恢复路径只允许启动一个原生产 Runtime Host，让正式 reconciler 对已经 fenced 的 generation
执行资源释放；只读观察三项均变为 `released / observed_release=true` 后停止该 Host，再以同一 operation 做
只读 `process-disable` 终态恢复和 audit。由于首次本地领取已先冻结 exact eventId intent，恢复逻辑必须接受
该不可变 intent 并返回 `claimedByHost=false / resendDisable=false`；不得把它改写成 Host 领取。若 Host 不唯一、
Receipt/route/operation 漂移或资源状态为 unknown，立即停止。
