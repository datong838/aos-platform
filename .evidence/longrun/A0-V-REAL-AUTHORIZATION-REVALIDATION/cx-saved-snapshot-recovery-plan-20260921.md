# CX 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `702a23e4`；CX installation `2e374e12-7523-466d-aed7-bdabe8b69aff` /
  generation `222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc`，binding rev6/epoch3
  enabled/ready，九路 rev273/group300，attempt=0；唯一外置 Runtime Host PID 36763
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 CW installation `0d5d5a7f-6e40-4725-b337-b79acc7d896a` rev211
  disabled/hash `sha256:ba6bc2d3e788809ebfc2624fd9b3984440c0d93f578627cc5ebe7bd8d5014260`；
  recovery rev69/hash `sha256:d03e6744c2d58040157332409945c6d67073eba4a5b5592a96459d6eeba276f5`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CX 正式退休与 CY direct successor。不使用定时 wake。
  本波无页面改动，不开自控浏览器。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CX、CW definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 36763 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CW rev211/recovery69 执行 transfer -> CX rev212 disabled、
   renew -> recovery70 / definition rev213 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev214 disabled；落 verification、测试、
   精确提交；自动进入 CX 正式退休与 CY direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
