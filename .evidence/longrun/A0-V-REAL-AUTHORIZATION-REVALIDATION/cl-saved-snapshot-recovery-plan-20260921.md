# CL 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `dde14d6c`；CL installation `64e49f66-b0ef-4676-91c1-eb05f6d1d0b1` /
  generation `a583218d-f65b-4697-9e60-7281a0bff66e`，binding rev6/epoch3 enabled/ready，
  九路 rev237/group264，attempt=0；唯一外置 Runtime Host PID 94133 保持在线。
- definition rev178 disabled/hash
  `sha256:85bc2d60525a8ad8866655367d31e5df62eef90aea048fb5ae9897ac473b5ff4`；recovery
  rev58/hash `sha256:b2a6a614463c337ec75e54dcedd7269332f9f54c33c3005c2296b72965081eb8`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用
  `run_definition`。
- 上一 attempt 终态为 **rev5**；guard overlay 仍需 predecessor_view revision=4，以适配
  共享 CB classify。本波仍属 BG-00 生命周期实证。封板后自动进入 CL 正式退休与 CM
  direct successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CL、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 94133 不动，启动受控纯 HTTP API；读回 Cron=false、
   snapshot worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、
   controls 后关闭 API。
3. **冻结输入转移**：从 CK rev178/recovery58 执行 transfer -> CL rev179 disabled、renew ->
   recovery59 / definition rev180 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev181 disabled；落 verification、测试、
   精确提交；自动进入 CL 正式退休与 CM direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、
负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
