# BN 保存快照恢复冻结验证（2026-09-20）

## 1. 结论

`BN_SAVED_SNAPSHOT_NOT_STARTED_RELEASED_BOUNDARY_FROZEN`。本波未 transfer、未 renew、未
enable definition、未产生 attempt，也未读取商城源数据。definition 保持 rev118 disabled。

纯 HTTP 18181 已成功验证 Cron=false、snapshot worker=false、进程内 Runtime Host=false，
sourceCalls=0、runsCreated=0；18181 随后正常关闭并释放。执行时曾误把“第二 Runtime Host=0”
解释为“外置 Host=0”，正常停止唯一 Host 导致 BN 三个 runtime resource lease 被正式释放；
该结果确定且不可伪造恢复，因此按 fail-closed 停止本波。

## 2. 精确冻结边界

- BN installation `d89bca67-4472-4b43-b0bd-ae8a2e0459f5` / generation
  `a43b3e64-7bb4-454c-822e-58bc13acbcaa`。
- binding 从 rev6/epoch3 enabled/ready 自然推进为 rev7/epoch4 disabled/fenced，
  desired_state 仍为 enabled、observed_state=unknown。
- 三个资源均为 released/observed_release=true；四个 lifecycle operation 保持 terminal succeeded。
- definition `cb0dba8c-803f-5caf-8011-b763d349f2ba` 保持 rev118 disabled；BN attemptCount=0。
- 恢复同一 singleton Host只读证明 liveTargets=[]、所有 business worker accepted/candidates=0，随后
  正常 `RUNTIME_HOST_STOPPED`；最终 18181=0、Runtime Host=0、第二 Host=0。

## 3. 失败点与无副作用

- 第一次 prepare 在旧凭据引用处、preview/intent/write 之前 fail-closed；BN adapter 注入新
  credentials/bundle/trust 后，第二次 prepare 在 exact binding 门拒绝 rev7/epoch4，仍未生成
  prepare result、未写数据库。
- 未调用 `run_definition`，未更换 definition idempotency key，未创建 worker/supervisor/attempt。
- 十二 Run 与十二 Dataset Receipt 的既有边界未被本波执行器修改；Store Receipt、ecom_link、
  projection 与负租户均未获得写入授权。

## 4. 自测与下一波

- BN pure HTTP 与 saved-recovery adapter 测试 2 passed；适配器保留用于审计，不允许在当前
  released binding 上执行 transfer。
- 下一波先形成新 plan，正式退休已释放且无 attempt 的 BN；随后从 exact BN successor/cutover
  authority 创建 BO direct successor，恢复一个受控 Runtime Host并重新达到 ready/健康边界。
  只有 BO 完成 verification 与提交后，才重新规划 BO saved-snapshot recovery。
