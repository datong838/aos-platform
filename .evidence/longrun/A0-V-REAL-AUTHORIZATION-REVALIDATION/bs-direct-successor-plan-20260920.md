# BR 正式退休与 BS direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `116ed18d`；BR installation `fddfa0b0-158c-4271-b1ea-dc4e1e36e293` / generation
  `981d7a2d-3bbe-4cc1-a8d9-c872be0147d3`，binding rev6/epoch3 enabled/ready，九路
  rev177/group204，三项 live resource，唯一外置 Runtime Host PID 26889。
- 唯一 attempt `256207c9-4bc4-4c89-b00f-146f58012011` 已正式 failed rev8，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev127 disabled，recovery
  rev41；自然 worker已停止。
- 12 members、12 running Run、12 Dataset Receipt保持；本快照组 Store Receipt=0、`ecom_link=0`、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：冻结上述 exact authority；核对 m1 单写者、唯一 Host、worker=0、18181=0。
2. **BR Host 释放与正式退休**：精确终止 PID 26889，读回 released-owner rev7/epoch4和三资源 released；
   以唯一 failed attempt、definition rev127、九路 rev177/group204执行正式 disable settlement，目标
   binding rev9/epoch5、legacy rev179/group206，并取得唯一 fence/detach Receipt。
3. **BS 创建与 lifecycle**：只以 BR detach Receipt为 predecessor，创建新的 installation/generation；
   串行 prepare、verify、stage、configure、enable，任何治理过期均走正式续期路径，不绕过门禁。
4. **注册与九路 cutover**：以唯一 idempotency key注册 BS；串行 approve、prepare、pause、commit、
   validate、resume，目标九路 rev180/group207，禁止重复切换。
5. **唯一 Host 与健康观察**：只启动一个外置 Runtime Host，第二 Host=0、18181=0；以只读、
   repeatable-read观察 lease renewal、binding ready、route一致和 attempt=0。
6. **verification/commit**：读回12/12与全部零副作用，落 verification、测试、精确提交；自动进入
   BS saved-snapshot recovery。

## 3. 停止条件

任一 identity/Receipt/hash/revision/attempt/Run/route漂移，出现第二Host/worker、商城源读取、负租户写、
业务副作用、未知提交边界或手工执行时立即fail closed。未知结果不得重发或更换幂等键；不push、不动其他
分支，230 L0继续挂起。非人工决策的工程问题由当前唯一开发最小修复并继续。
