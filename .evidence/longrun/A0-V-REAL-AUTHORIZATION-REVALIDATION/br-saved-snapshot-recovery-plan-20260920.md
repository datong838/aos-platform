# BR 保存快照恢复与单一自然 attempt 方案（2026-09-20）

## 1. 当前权威

- HEAD `1f832030`；BR installation `fddfa0b0-158c-4271-b1ea-dc4e1e36e293` /
  generation `981d7a2d-3bbe-4cc1-a8d9-c872be0147d3`，binding rev6/epoch3 enabled/ready，
  九路 rev177/group204，attempt=0；唯一外置 Runtime Host PID 26889。
- definition rev124 disabled/hash
  `sha256:6472cbec4f4a3dcf31540bf54ea3f1ca03d832dcc4c601d54d7dfb508a26d353`；
  recovery rev40/hash `sha256:ac3656e9f5b9852b438a43adad574c2a30e6b80420282b196dd51a5605ecff97`。
  该冻结输入仍指向 BP predecessor，因为 BQ 在 transfer 写入口前已安全退休。
- 12 members、12个仍running的保存Run、12 Dataset Receipt保持；本快照组 Store Receipt=0、
  `ecom_link=0`、projection pending=0、canary=0。BudgetPolicy/RuntimePolicy rev10当前有效。
- 本波只转移既有冻结输入，不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述 BR、definition/recovery、attempt=0、零副作用、m1单写者与一个Host。
2. **纯HTTP 18181**：并存启动受控纯HTTP API；读回Cron=false、snapshot worker=false、进程内Host=false；
   外置Host总数恰好1，第二Host=0。prepare、schedule-ingest、controls完成后关闭并确认端口释放。
3. **冻结输入转移**：从 BP rev124/recovery40执行 transfer -> BR rev125 disabled、renew -> recovery41 /
   definition rev126 enabled，全部读回 `sourceReads=0`。
4. **唯一自然worker**：创建exact lease与BR专用supervisor，禁止手工`run_definition`、第二worker/Host/attempt；
   worker在unknown tick后停止本轮serve。
5. **连续观察**：50秒只读采样至正式terminal；仅当300秒
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`且12 Run与零副作用不变时，在原accepted_at起算1800秒内
   继续同一attempt，绝不重发。
6. **终态/verification/commit**：正式终态后stop-only推进rev127 disabled；落verification、测试、精确
   提交，自动进入BR正式退休与BS direct successor。

## 3. 停止条件

任一identity/Receipt/hash/revision/Run/route漂移，出现第二Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界、配置治理再次过期或手工执行时立即fail closed；未知结果不得重发或换幂等键。
不push、不动其他分支，230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
