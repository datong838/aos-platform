# CI 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `64084809`；CI installation `1b9f500d-48a0-4f2c-8284-3db26e5cd4e7` /
  generation `8de8994b-ad87-4039-a851-d944153bca08`，binding rev6/epoch3 enabled/ready，
  九路 rev228/group255，attempt=0；唯一外置 Runtime Host PID 85436 保持在线。
- definition rev169 disabled/hash
  `sha256:807d42c9500373612589a1ba0d5f436df8d064ef6190b9b2a9c3e58474a127bd`；recovery
  rev55/hash `sha256:9b479ea57323740d9fc9afd4a74474a32e405dbbe0b68cc675edbc2bcefc7ebb`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用
  `run_definition`。
- 本波仍属 BG-00 生命周期实证，不宣称黄埔 0 期经营首链完成。封板后自动进入 CI 正式退休与
  CJ direct successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CI、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 85436 不动，启动受控纯 HTTP API；读回 Cron=false、
   snapshot worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、
   controls 后关闭 API。
3. **冻结输入转移**：从 CH rev169/recovery55 执行 transfer -> CI rev170 disabled、renew ->
   recovery56 / definition rev171 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev172 disabled；落 verification、测试、
   精确提交；自动进入 CI 正式退休与 CJ direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、
负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
