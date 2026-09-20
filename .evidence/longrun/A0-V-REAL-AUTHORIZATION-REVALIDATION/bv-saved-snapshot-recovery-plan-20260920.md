# BV 保存快照恢复与单一自然 attempt 方案（2026-09-20）

## 1. 当前权威

- HEAD `4055a7da`；BV installation `2b1aa826-b595-40d4-aeb2-9a7ce9d33c36` /
  generation `e8a5b32b-9a29-41bf-9c7f-87c7cd96b359`，binding rev6/epoch3 enabled/ready，
  九路 rev189/group216，attempt=0；唯一外置 Runtime Host PID 15565保持在线。
- definition rev130 disabled/hash
  `sha256:5a07cdb9584a79f3f51fefc33a5ece622700c08cde8799eb522beff59c857392`；recovery
  rev42/hash `sha256:2f137e718e768aa98116af8dfa8c28a5eb66d2f3270fe8ac4c1f87b16d7cd963`。
  冻结输入仍指向BU predecessor；BV尚未进入transfer写入口。
- 12 members、12个仍running的保存Run、12 Dataset Receipt；本快照组 Store Receipt=0、
  `ecom_link=0`、projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，
  不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定BV、definition/recovery、attempt=0、零副作用与唯一Host在线边界。
2. **纯HTTP 18181并存**：保持PID 15565不动，启动受控纯HTTP API；读回Cron=false、snapshot
   worker=false、进程内Host=false，外置Host总数恰好1、第二Host=0；完成prepare、schedule-ingest、
   controls后关闭API并确认18181释放。
3. **冻结输入转移**：从BU rev130/recovery42执行transfer -> BV rev131 disabled、renew -> recovery43 /
   definition rev132 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然worker**：创建BV exact attempt guard、worker与supervisor；保持既有Host，证明第二Host=0、
   worker=0、attempt=0后仅启动一个自然worker，禁止手工 `run_definition`。
5. **连续观察**：50秒只读采样至唯一attempt正式terminal；若300秒仅因
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`且12 Run与零副作用不变，则按原accepted_at在1800秒预算内
   延续同一attempt，绝不重发。
6. **终态/verification/commit**：正式终态后stop-only推进definition rev133 disabled；落
   verification、测试、精确提交；自动进入BV正式退休与BW direct successor。

## 3. 停止条件

任一identity/Receipt/hash/revision/Run/route漂移，出现第二Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界、配置治理过期或手工执行时立即fail closed；未知结果不得重发或换幂等键。
不push、不动其他分支，230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
