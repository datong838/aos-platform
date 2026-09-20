# BW 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `254ba795`；BW installation `9b6e1277-a0a2-447d-9062-a98adfed3f22` /
  generation `62cf014b-9ce5-4512-8a34-b55a79e053c3`，binding rev6/epoch3 enabled/ready，
  九路 rev192/group219，attempt=0；唯一外置 Runtime Host PID 20193保持在线。
- definition rev133 disabled/hash
  `sha256:353ea9fb1da5f282c1b70f77f90b2e79cf26f279648934836d524c512c899528`；recovery
  rev43/hash `sha256:4a14bb3109516487c5ede4ee27a131f0c27043ce6daed1e880fcd1222b303625`。
  冻结输入仍指向BV predecessor；BW尚未进入transfer写入口。
- 12 members、12个仍running的保存Run、12 Dataset Receipt；本快照组 Store Receipt=0、
  `ecom_link=0`、projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，
  不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定BW、definition/recovery、attempt=0、零副作用与唯一Host在线边界。
2. **纯HTTP 18181并存**：保持PID 20193不动，启动受控纯HTTP API；读回Cron=false、snapshot
   worker=false、进程内Host=false，外置Host总数恰好1、第二Host=0；完成prepare、schedule-ingest、
   controls后关闭API并确认18181释放。
3. **冻结输入转移**：从BV rev133/recovery43执行transfer -> BW rev134 disabled、renew -> recovery44 /
   definition rev135 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然worker**：创建BW exact attempt guard、worker与supervisor；保持既有Host，证明第二Host=0、
   worker=0、attempt=0后仅启动一个自然worker，禁止手工 `run_definition`。
5. **连续观察**：50秒只读采样至唯一attempt正式terminal；若300秒仅因
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`且12 Run与零副作用不变，则按原accepted_at在1800秒预算内
   延续同一attempt，绝不重发。
6. **终态/verification/commit**：正式终态后stop-only推进definition rev136 disabled；落
   verification、测试、精确提交；自动进入BW正式退休与BX direct successor。

## 3. 停止条件

任一identity/Receipt/hash/revision/Run/route漂移，出现第二Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界、配置治理过期或手工执行时立即fail closed；未知结果不得重发或换幂等键。
不push、不动其他分支，230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
