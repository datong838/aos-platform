# CS 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `ccea6c1f`；CS installation `ff72acba-1e59-4da3-b92a-18737e18e9d2` /
  generation `01a1719d-1109-440f-a233-1c5a6adb0d81`，binding rev6/epoch3
  enabled/ready，九路 rev258/group285，attempt=0；唯一外置 Runtime Host PID 16307
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 CR installation `913cb7a1-4912-471a-abbf-452e3ce999a9` rev196
  disabled/hash `sha256:7800cc53151703efb5b85b9ef3652d79614745632475ec77846d4148cbc616b2`；
  recovery rev64/hash `sha256:a7ac1581109526f9ebcf492ab38264a892ca6ec732bbfd773c1fa8a8b388b4dd`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev5**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CS 正式退休与 CT direct successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CS、CR definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 16307 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CR rev196/recovery64 执行 transfer -> CS rev197 disabled、
   renew -> recovery65 / definition rev198 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev199 disabled；落 verification、测试、
   精确提交；自动进入 CS 正式退休与 CT direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
