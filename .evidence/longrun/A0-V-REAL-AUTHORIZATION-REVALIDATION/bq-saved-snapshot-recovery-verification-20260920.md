# BQ 保存快照恢复安全停止验证（2026-09-20）

## 结论

`BQ_SAVED_SNAPSHOT_RECOVERY_SAFE_STOPPED_PRE_TRANSFER`。

BQ 在纯 HTTP 阶段完成后、冻结输入 transfer 开始前，唯一外置 Runtime Host 因健康检查超时已按
fail-closed 规则释放当前 generation。transfer 的首次调用在任何写入前被
`runtime request is not currently admitted` 拒绝；definition 仍为 rev124 disabled，BQ attempt=0，
因此不存在未知提交、重复 attempt 或需重发的边界。该 generation 不允许原地复活，本波按方案停止条件
冻结，下一波转入 BQ released-owner 正式退休与 BR direct successor。

## 1/6 plan 与前置基线

- HEAD `49aef9e6`，BQ installation `4faaf3b7-2d10-4961-99db-5bf52b7b8a63` / generation
  `b53ce5ac-169c-4d69-9780-58beb8ad736c`。
- plan 固定 definition rev124 disabled、recovery rev40/hash
  `sha256:ac3656e9f5b9852b438a43adad574c2a30e6b80420282b196dd51a5605ecff97`、attempt=0，
  以及 transfer rev125 / recovery rev41 / enabled rev126 / paused rev127 的目标序列。
- BQ 专用受控 API、保存快照执行器与专项测试先落盘；语法编译通过，保存快照/退休回归 29 项通过。

## 2/6 纯 HTTP 18181

- 18181 `/openapi.json` 返回200；读回 `AOS_QYH_CRON_ENABLED=false`、
  `AOS_SNAPSHOT_GROUP_WORKER_ENABLED=false`、`AOS_EXTENSION_RUNTIME_HOST_ENABLED=0`，
  `sourceCalls=0/runsCreated=0`。
- `prepare` 形成12个只读 draft；`schedule-ingest` 确认12个既有 schedule；`controls` 读回12组
  selection/control/binding，未读取商城源数据。
- 纯 HTTP 进程随后关闭，18181 listener=0；全程没有进程内 Host、snapshot worker 或 attempt。

## 3/6 transfer 前安全停止

- 前置进程核对发现上一波唯一 Host PID 94724 已退出；其 status-file 为
  `HOST_RUNTIME_FAILED`，因 health check `TimeoutError` 进入清理。
- 数据库权威已收敛为 binding rev7/epoch4、`enabled=false`、`operation_fence=true`、
  `desired_state=enabled`、`observed_state=unknown`；三项资源均
  `released/observed_release=true`。该 released generation 禁止原地复活。
- 为区分“Host 暂时缺失”与“代际已释放”，曾以既有凭据、bundle 与信任根启动唯一诊断 Host
  PID 20146；status 为 ACTIVE 但 `liveTargets=[]`。transfer 在 `service.options` 的只读准入检查中
  抛出 `PermissionError: runtime request is not currently admitted`，没有进入
  `transfer_saved_recovery`，且 `transfer-result.json` 未生成。
- 诊断 Host 已收到 SIGINT 并以 `RUNTIME_HOST_STOPPED` 正常退出；最终外置 Host=0，18181=0。

## 4/6 与 5/6 未执行

- 未创建 definition rev125、recovery rev41、definition rev126/rev127；未启动 snapshot worker、
  supervisor 或自然 attempt，也未调用 `run_definition`。
- 最终只读边界：definition rev124 disabled；BQ attempt=0；12 members、12 个仍 running 的保存
  Run、12 Dataset Receipt保持；本快照组 link Store Receipt=0、`ecom_link=0`、projection pending=0、
  `dev-org/dev-project` canary=0。主库历史 Store Receipt总数不作为本波零副作用指标。

## 6/6 收笔与下一波

- 本波不是恢复 GREEN，而是严格命中 plan 停止条件后的安全冻结；失败发生在写入口之前，故不存在
  unknown result、幂等键重发或手工补跑。
- 下一波自动执行 **BQ released-owner 正式退休与 BR direct successor**：先以 binding rev7、三资源
  released、definition rev124 disabled、attempt=0 为 exact authority，走正式
  `preflight -> request-disable -> process-disable -> audit`；取得 fence/detach Receipt 后才创建 BR，
  完成 lifecycle、九路 cutover 与有界健康观察。
- 不 push、不动其他分支；230 L0继续挂起，商城源数据未读取。
