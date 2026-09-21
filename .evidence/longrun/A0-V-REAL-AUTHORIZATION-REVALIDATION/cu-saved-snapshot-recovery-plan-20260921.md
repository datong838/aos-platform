# CU 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `e4aab6f0`；CU installation `2c2d5506-1f80-4557-bf4b-00ead0258002` /
  generation `bcaa7ea0-62b1-4238-8615-28db45e3014e`，binding rev6/epoch3
  enabled/ready，九路 rev264/group291，attempt=0；唯一外置 Runtime Host PID 22753
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 CT installation `b4847c85-b452-4c87-bf56-8a57bc9f8d25` rev202
  disabled/hash `sha256:9b95e4daa15bfb4dc5783c42a8b8557e05bd96522dd4bed452882d349ebcd0f5`；
  recovery rev66/hash `sha256:8090c986e3c22b2548a14e793dc8376230bdb262aedd84f10083e2139605230a`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev5**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CU 正式退休与 CV direct successor。不使用定时 wake。
  本波无页面改动，不开自控浏览器。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CU、CT definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 22753 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CT rev202/recovery66 执行 transfer -> CU rev203 disabled、
   renew -> recovery67 / definition rev204 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev205 disabled；落 verification、测试、
   精确提交；自动进入 CU 正式退休与 CV direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
