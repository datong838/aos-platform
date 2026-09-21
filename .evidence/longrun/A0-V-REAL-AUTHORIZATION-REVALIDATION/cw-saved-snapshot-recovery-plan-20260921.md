# CW 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `eb54dafc`；CW installation `0d5d5a7f-6e40-4725-b337-b79acc7d896a` /
  generation `a60036f1-5887-4157-ad32-616925b547bf`，binding rev6/epoch3
  enabled/ready，九路 rev270/group297，attempt=0；唯一外置 Runtime Host PID 32943
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 CV installation `f94149ca-a01e-4a20-836f-3f5132e0dbb7` rev208
  disabled/hash `sha256:579cce9df45c51b3db39d85b1456fc21364cef67561f20155e360255c3b4f8df`；
  recovery rev68/hash `sha256:741c9bffd2ee51a680fd7617638e35f32d461c241e0cd95692a660c49f68caa1`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CW 正式退休与 CX direct successor。不使用定时 wake。
  本波无页面改动，不开自控浏览器。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CW、CV definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 32943 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CV rev208/recovery68 执行 transfer -> CW rev209 disabled、
   renew -> recovery69 / definition rev210 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev211 disabled；落 verification、测试、
   精确提交；自动进入 CW 正式退休与 CX direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
