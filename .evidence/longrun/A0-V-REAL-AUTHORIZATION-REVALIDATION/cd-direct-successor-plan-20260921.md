# CC 正式退休与 CD direct successor 方案（2026-09-21）

## 1. 当前权威

- HEAD `bd8e4b84`；CC installation `03942567-0f78-4530-b9dd-634bec59c780` / generation
  `c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2`，binding rev6/epoch3 enabled/ready，九路
  rev210/group237，三项 live resource。电脑重启后已确认原唯一外置 Runtime Host PID 38020 不存在；
  该进程消失不等于资源已释放，必须由正式 disable Owner 读回并收敛。
- 唯一 attempt `74ee33d8-b0d4-444a-9c01-ba31e9358552` 已正式 failed rev4，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev154 disabled，recovery50，
  自然 worker 已停止。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection
  pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：冻结上述 exact authority；核对 m1 单写者、重启后 Host 进程=0、worker=0、18181=0。
2. **CC 正式退休**：不得伪造 SIGTERM；对已经消失的 PID 只做事实记录，以唯一 failed attempt、definition
   rev154、九路 rev210/group237 执行正式 disable settlement，目标 binding rev9/epoch5、legacy
   rev212/group239，并取得唯一 fence/detach Receipt；资源必须读回 released。
3. **CD 创建与 lifecycle**：仅以 CC detach Receipt 为 predecessor 创建新 installation/generation；串行
   prepare、verify、stage、configure、enable；prepare accepted 后只启动唯一外置 Host 自然领取。
4. **注册与九路 cutover**：唯一幂等键注册 CD；串行 approve、prepare、pause、commit、validate、resume，
   目标九路 rev213/group240，禁止重复切换。
5. **唯一 Host 与健康观察**：第二 Host=0、18181=0、snapshot worker=0；只读 repeatable-read 观察
   lease renewal、binding ready、route 一致与 attempt=0。
6. **verification/commit**：读回 12/12 与全部零副作用，落 verification、测试、精确提交；自动进入 CD
   saved-snapshot recovery。

## 3. 停止条件

任一 identity/Receipt/hash/revision/attempt/Run/route 漂移，正式退休后资源非 released，出现第二 Host/worker、
商城源读取、负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发或更换
幂等键；不 push、不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
