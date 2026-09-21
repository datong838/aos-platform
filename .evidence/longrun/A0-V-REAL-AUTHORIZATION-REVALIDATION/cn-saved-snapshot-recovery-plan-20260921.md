# CN 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `f348c90a`；CN installation `1366f4dd-47d9-42c1-b26a-759c7bd556da` /
  generation `cd0601e0-2668-496d-9f93-561d2e69a170`，binding rev6/epoch3 enabled/ready，
  九路 rev243/group270，attempt=0；唯一外置 Runtime Host PID 519 保持在线。
- definition rev184 disabled/hash
  `sha256:7c559d8b95bae85dca4bea7e66a398b93cd6d7c8f47a48f0948321eb717a9dec`；recovery
  rev60/hash `sha256:f372ccc196603b610e1a32c0323e3deb2bb43ef1dae561123adc6b7cfdc3b083`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用
  `run_definition`。
- 上一 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4，以适配
  共享 CB classify。pause 后 live definition 为 disabled，classify 叠加
  `definitionState=enabled`。本波仍属 BG-00 生命周期实证。封板后自动进入 CN 正式退休与 CO
  direct successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CN、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 519 不动，启动受控纯 HTTP API；读回 Cron=false、
   snapshot worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、
   controls 后关闭 API。
3. **冻结输入转移**：从 CM rev184/recovery60 执行 transfer -> CN rev185 disabled、renew ->
   recovery61 / definition rev186 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev187 disabled；落 verification、测试、
   精确提交；自动进入 CN 正式退休与 CO direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、
负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
