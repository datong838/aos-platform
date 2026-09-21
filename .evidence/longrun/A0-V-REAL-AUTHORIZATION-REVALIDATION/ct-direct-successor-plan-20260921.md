# CS 正式退休与 CT direct successor 方案（2026-09-21）

## 1. 当前权威

- HEAD `7e94d392`；CS installation `ff72acba-1e59-4da3-b92a-18737e18e9d2` / generation
  `01a1719d-1109-440f-a233-1c5a6adb0d81`，binding rev6/epoch3 enabled/ready，九路
  rev258/group285，三项 live resource，唯一外置 Runtime Host PID 16307。
- 唯一 attempt `b7d12c25-6673-48b3-aaba-dc803edb9169` 已正式 failed **rev5**，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev199 disabled、
  recovery65，自然 worker 已停止。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 本波仍属 BG-00 生命周期实证；全程唯一开发，封板后自动进入 CT saved-snapshot recovery。
  不使用定时 wake。

## 2. 串行步骤 1-6

1. **plan/preflight**：冻结上述 exact authority；核对 m1 单写者、唯一 Host、worker=0、18181=0。
2. **CS Host 释放与正式退休**：精确终止 PID 16307，读回 released-owner rev7/epoch4 与三资源
   released；以唯一 failed attempt **rev5**、definition rev199、九路 rev258/group285 执行正式 disable
   settlement，目标 binding rev9/epoch5、legacy rev260/group287，并取得唯一 fence/detach Receipt。
   退休 preflight 前不得创建 `replacement-ct` 目录。
3. **CT 创建与 lifecycle**：仅以 CS detach Receipt 为 predecessor 创建新 installation/generation；
   串行 prepare、verify、stage、configure、enable；prepare accepted 后只启动唯一外置 Host 自然领取。
   CT configuration 必须引用 current RuntimePolicy rev11，使后续 saved-snapshot prepare 仍落在
   Binding rev6/epoch3。
4. **注册与九路 cutover**：唯一幂等键注册 CT；串行 approve、prepare、pause、commit、validate、
   resume，目标九路 rev261/group288，禁止重复切换。
5. **唯一 Host 与健康观察**：第二 Host=0、18181=0、snapshot worker=0；只读 repeatable-read
   观察 lease renewal、binding ready、route 一致与 attempt=0。health baseline 必须是当时 live
   renewals，目标 +12。
6. **verification/commit**：读回 12/12 与全部零副作用，落 verification、测试、精确提交；
   自动进入 CT saved-snapshot recovery。

## 3. 停止条件

任一 identity/Receipt/hash/revision/attempt/Run/route 漂移，Host 停止后资源非 released，出现第二
Host/worker、商城源读取、负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。
未知结果不得重发或更换幂等键；不 push、不动其他分支，230 L0 继续挂起；非人工决策工程问题
由当前唯一开发最小修复并继续。不使用定时 wake。
