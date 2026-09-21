# CD 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `16a5c6e6`；CD installation `01b41c17-fce2-4bcf-8d9e-a48d2d4bf743` /
  generation `22639b06-1211-424d-9f64-696822e0add4`，binding rev6/epoch3 enabled/ready，
  九路 rev213/group240，attempt=0；唯一外置 Runtime Host PID 58751 保持在线。
- definition rev154 disabled/hash
  `sha256:50d59d0646f3840e9e4eca7f0eca318cf90fc6f93c0deb46aa12fce166258e4b`；recovery
  rev50/hash `sha256:bd94a859c10729c3b988c714a29441c823dcaab85f33c005f69d7aecdd25cad8`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0、
  canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CD、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 58751 不动，启动受控纯 HTTP API；读回 Cron=false、snapshot
   worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CC rev154/recovery50 执行 transfer -> CD rev155 disabled、renew -> recovery51 /
   definition rev156 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev157 disabled；落 verification、测试、精确提交；
   自动进入 CD 正式退休与 CE direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、不动其他分支，
230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
