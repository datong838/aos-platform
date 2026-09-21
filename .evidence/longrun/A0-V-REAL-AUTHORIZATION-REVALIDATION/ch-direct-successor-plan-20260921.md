# CG 正式退休与 CH direct successor 方案（2026-09-21）

## 1. 当前权威

- HEAD `680286f1`；CG installation `8f42819c-0fc7-48cf-a5c4-9ba96894a6f5` / generation
  `3ed300fa-5fff-4949-9fb0-1926412e51ae`，binding rev6/epoch3 enabled/ready，九路
  rev222/group249，三项 live resource，唯一外置 Runtime Host PID 77505。
- 唯一 attempt `f7b2fc7f-9bce-4102-8f5b-48ec8879ae55` 已正式 failed rev4，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev166 disabled、
  recovery54，自然 worker 已停止。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 本波仍属 BG-00 生命周期实证；全程唯一开发，封板后自动进入 CH saved-snapshot recovery。

## 2. 串行步骤 1-6

1. **plan/preflight**：冻结上述 exact authority；核对 m1 单写者、唯一 Host、worker=0、18181=0。
2. **CG Host 释放与正式退休**：精确终止 PID 77505，读回 released-owner rev7/epoch4 与三资源
   released；以唯一 failed attempt、definition rev166、九路 rev222/group249 执行正式 disable
   settlement，目标 binding rev9/epoch5、legacy rev224/group251，并取得唯一 fence/detach Receipt。
3. **CH 创建与 lifecycle**：仅以 CG detach Receipt 为 predecessor 创建新 installation/generation；
   串行 prepare、verify、stage、configure、enable；prepare accepted 后只启动唯一外置 Host 自然领取。
4. **注册与九路 cutover**：唯一幂等键注册 CH；串行 approve、prepare、pause、commit、validate、
   resume，目标九路 rev225/group252，禁止重复切换。
5. **唯一 Host 与健康观察**：第二 Host=0、18181=0、snapshot worker=0；只读 repeatable-read
   观察 lease renewal、binding ready、route 一致与 attempt=0。
6. **verification/commit**：读回 12/12 与全部零副作用，落 verification、测试、精确提交；
   自动进入 CH saved-snapshot recovery。

## 3. 停止条件

任一 identity/Receipt/hash/revision/attempt/Run/route 漂移，Host 停止后资源非 released，出现第二
Host/worker、商城源读取、负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。
未知结果不得重发或更换幂等键；不 push、不动其他分支，230 L0 继续挂起；非人工决策工程问题
由当前唯一开发最小修复并继续。
