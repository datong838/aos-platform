# BN released retirement 与 BO direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `6e38a1e7`。BN installation `d89bca67-4472-4b43-b0bd-ae8a2e0459f5` /
  generation `a43b3e64-7bb4-454c-822e-58bc13acbcaa` 仍 active rev5/etag5，但 binding 已为
  rev7/epoch4 disabled/fenced/desired enabled/observed unknown，三资源 released。
- 九路仍指向 BN extension rev165/group192；definition rev118 disabled；BN attempt=0，tenant
  running/claimed/unknown/runtime pending=0，十二 Run/Receipt 与业务零副作用边界保持。
- Runtime Host=0、18181=0。`.2` canonical bundles、新 trust root 与四类新凭据有效。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述 released BN、route/definition/attempt/业务边界和单写者状态。
2. **正式 disable/detach**：复用 released-owner settlement，先 request-disable，后由唯一固定 consumer
   处理 exact delivery；预期 binding rev9/epoch5 desired disabled，九路 legacy rev167/group194，
   fence=true，lifecycle receipts 精确为 fence/detach。禁止重发未知 operation。
3. **创建 BO**：以 BN exact detach Receipt 为 predecessor，使用 canonical `.2` 四坐标创建 BO；启动
   一个 Runtime Host，串行 prepare/verify/stage/configure/enable，第二 Host=0。
4. **注册与切换**：以 BN detach Receipt 注册 BO successor；按 approve -> prepare -> pause -> commit ->
   validate -> resume，目标九路 extension rev168/group195。
5. **健康观察**：definition rev118 继续 disabled；至少 12 次新增 lease renewal，attempt=0、十二
   Run/Receipt 与 Store Receipt/ecom_link/projection pending=0、canary=0。
6. **verification/commit**：最终只读 observe、测试、verification 与精确提交；随后自动进入 BO
   saved-snapshot recovery，纯 HTTP 期间保持已有外置 Host=1、第二 Host=0。

## 3. 停止条件

- BN released facts、detach operation/receipt、route revision 或 definition 漂移；
- create/lifecycle/register/cutover 出现 unknown 或部分提交；
- 第二 Host、手工 `run_definition`、商城源读取、负租户写入或任何业务副作用；
- 不得以手工更新 binding/route 或复活 released resource 绕过正式 direct successor。

全程不 push、不动其他分支，230 L0继续挂起。所有非人工决策型工程阻断在上述边界内自主诊断、
最小修复并继续。

执行中读回补充：disable consumer 已提交后，实际 binding 为 rev9/epoch5；九路与两张 lifecycle
Receipt均符合预期。epoch 增量是正式 Owner 的 detach 语义，原 epoch4 断言已纠正；只走 completed
readback，`resendDisable=false`。
