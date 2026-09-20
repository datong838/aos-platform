# BY 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `1105b212`；BY installation `ed64db1a-45eb-442e-8f1b-49ed899731dc` /
  generation `01f99334-0515-4c73-b442-a293709b3cc2`，binding rev6/epoch3 enabled/ready，
  九路 rev198/group225，attempt=0；唯一外置 Runtime Host PID 29455 保持在线。
- definition rev139 disabled/hash
  `sha256:8986978b518d885bf6753510e1b38f6b860c8aeb5028309c9e3789fab351e7cf`；recovery
  rev45/hash `sha256:f00d142e1b579f6452bd7aa57ffdde273454ce2a4ed6a8cf6fe564f1ff0463da`。
  冻结输入仍指向 BX predecessor；BY 尚未进入 transfer 写入口。
- 12 members、12 个仍 running 的保存 Run、12 Dataset Receipt；本快照组 Store Receipt=0、
  `ecom_link=0`、projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，
  不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 BY、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 29455 不动，启动受控纯 HTTP API；读回 Cron=false、snapshot
   worker=false、进程内 Host=false，外置 Host 总数恰好 1、第二 Host=0；完成 prepare、schedule-ingest、
   controls 后关闭 API 并确认 18181 释放。
3. **冻结输入转移**：从 BX rev139/recovery45 执行 transfer -> BY rev140 disabled、renew -> recovery46 /
   definition rev141 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：创建 BY exact attempt guard、worker 与 supervisor；保持既有 Host，证明第二 Host=0、
   worker=0、attempt=0 后仅启动一个自然 worker，禁止手工 `run_definition`。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；若 300 秒仅因
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且 12 Run 与零副作用不变，则按原 accepted_at 在 1800 秒预算内
   延续同一 attempt，绝不重发。
6. **终态/verification/commit**：正式终态后 stop-only 推进 definition rev142 disabled；落
   verification、测试、精确提交；自动进入 BY 正式退休与 BZ direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界、配置治理过期或手工执行时立即 fail closed；未知结果不得重发或换幂等键。
不 push、不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
