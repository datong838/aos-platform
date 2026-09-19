# BD 单终态正式退休方案

## 当前权威

BD installation `c2d6ef97-30ec-4980-9421-54a899607853` / generation
`f5e01f1d-e6c5-425a-9145-6f7a82ec65e5` 仍为 active；Binding rev6/epoch3 enabled/ready/unfenced，
三资源 live，九路 extension rev138/group165。definition rev94 disabled，snapshot worker 已停止，18181 已释放。

固定 attempt 历史只有 revision 61 `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`。
十二 Run 仍 running、十二 Dataset Receipt 保留，Store Receipt、`ecom_link`、outbox、projection pending 与 canary
均为 0。本波只接受该 exact 边界。

## 文件级清单与顺序

1. 新增 `scripts/a0v_bd_terminal_retirement.py`：只注入 BD exact 身份、lock、单次 terminal attempt、
   definition rev94、active rev138/group165 与预期 detached rev140/group167；复用正式 AQ
   `preflight → request-disable → process-disable → audit` Owner 路径。
2. 新增专项测试，固定上述常量、单次 delivery、`resendDisable=false`、零 Store 边界和禁止
   `run_definition`。
3. 串行执行四步；request 只接受现有 Binding rev6/etag5，process 只允许唯一 Runtime Host 自然领取
   同一 disable operation，或在明确未领取时由原 RuntimeDisableConsumer 领取一次。
4. verification 落盘并精确提交后，才允许从 exact detach Receipt 规划 BE direct successor。

## 完成与停止条件

- attempt/definition/route/resource/hash 任一漂移立即停止；未知 Receipt 只读对账，不换幂等键。
- audit 必须读回 Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy
  rev140/group167、fence+detach 两张 Receipt、definition rev94 disabled、唯一 exact terminal attempt 与
  Store/ecom/projection/canary 全零。
- 不启动 snapshot worker，不创建第二 attempt，不读取商城源数据，不 push，不改其他分支；230 L0 继续挂起。
