# BA 单终态正式退休方案

## 当前权威

BA installation `9110f69b-bb31-4d17-98e8-6c5ed1d9234f` / generation
`197f5036-656a-4b58-a261-e93e2fffea18` 仍为 active；Binding rev6/epoch3 enabled/ready/unfenced，
三资源 live，九路 extension rev129/group156。definition rev85 disabled，snapshot worker 已停止，18181 已释放。

固定 attempt 历史只有 revision 61
`abandoned / ATTEMPT_LEASE_EXPIRED`。十二 Run 仍 running、十二 Dataset Receipt 保留，Store Receipt、
`ecom_link`、outbox、projection pending 与 canary 均为 0。上一波 monitor 重启导致 attempt elapsed=1909 秒；
本波只接受这个已披露的 exact terminal 边界，不把预算偏差改写为成功，也不恢复 BA worker。

## 文件级清单与顺序

1. 新增 `scripts/a0v_ba_terminal_retirement.py`：只注入 BA exact 身份、lock、单次 terminal attempt、
   definition rev85、active rev129/group156 与预期 detached rev131/group158；复用正式 AQ
   `preflight → request-disable → process-disable → audit` Owner 路径。
2. 新增专项测试，固定上述常量、单次 delivery、`resendDisable=false`、零 Store 边界和禁止
   `run_definition`。
3. 串行执行四步；request 只接受现有 Binding rev6/etag5，process 只允许唯一 Runtime Host 自然领取
   同一 disable operation，或在明确未领取时由原 RuntimeDisableConsumer 领取一次。
4. verification 落盘并精确提交后，才允许从 exact detach Receipt 规划 BB direct successor。

## 完成与停止条件

- attempt/definition/route/resource/hash 任一漂移立即停止；未知 Receipt 只读对账，不换幂等键。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy
  rev131/group158、fence+detach 两张 Receipt、definition rev85 disabled、唯一 exact terminal attempt 与
  Store/ecom/projection/canary 全零。
- 不启动 snapshot worker，不创建第二 attempt，不读取商城源数据，不 push，不改其他分支；230 L0 继续挂起。
