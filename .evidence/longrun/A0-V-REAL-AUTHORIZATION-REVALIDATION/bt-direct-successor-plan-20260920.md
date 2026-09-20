# BS uncertain-resource 正式退休与 BT direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `cd5b1dd2`；BS installation `c5a95204-c379-4763-b697-b4417349d204` / generation
  `6f8bcb56-5717-4d7a-9a9e-97c1982db053`，binding rev7/epoch4 disabled/fenced/desired enabled/
  observed unknown，Runtime Host=0，attempt=0，九路仍为BS extension rev180/group207。
- runtime-apply `0587d5e6-1f14-4406-a1e4-95e8e556c583` 为 rev20、phase succeeded、status
  needs_attention、failure `RESOURCE_CLEANUP_UNCERTAIN`；三资源中2 released，唯一 uncertain资源
  `accb54dc-6341-4dc7-b8da-40202a102569`。
- definition rev127 disabled；12 members、12 running Run、12 Dataset Receipt保持；本快照组 Store
  Receipt=0、`ecom_link=0`、projection pending=0、canary=0。

## 2. 串行步骤 1-6

1. **plan/exact cleanup preflight**：固定上述operation/resource/binding/route/零副作用及Host=0边界。
   重启后读回必须通过 `consumer_connection` 建立 `org-org/dev-project` 租户作用域；禁止把
   `aos_runtime` 在RLS下的不可见行误判为记录缺失，且该修复不得改变正式资源恢复行为。
2. **正式资源恢复与BS退休**：只对唯一过期uncertain资源调用 `ExpiredResourceRecovery`；正式恢复
   会为该资源写入唯一 `resource_released` 事件并把operation推进至rev21。三资源均released后以
   CAS rev21调用 `settle_committed_cleanup`，目标operation failed rev22/
   `PREPARED_RUNTIME_RELEASED`。随后正式disable settlement，目标binding rev9/epoch5与legacy
   rev182/group209，并取得唯一detach Receipt。
3. **BT 创建与 lifecycle**：仅以BS detach Receipt为predecessor，串行创建、prepare、verify、stage、
   configure、enable；任何未知结果不重发。
4. **注册与九路 cutover**：唯一注册幂等键，串行approve、prepare、pause、commit、validate、resume，
   目标九路rev183/group210。
5. **唯一Host与健康观察**：只启动一个外置Host，第二Host=0、18181=0；只读观察lease renewal、
   binding ready、routes与attempt=0。
6. **verification/commit**：读回12/12及全部零副作用，落verification、测试、精确提交；自动进入
   BT saved-snapshot recovery。

## 3. 停止条件

资源仍live/uncertain、cleanup proof或CAS revision漂移、出现第二Host/attempt、商城源读取、负租户写、
业务副作用或未知提交边界时立即fail closed；不得原地复活BS或重发未知请求。不push、不动其他分支，
230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
