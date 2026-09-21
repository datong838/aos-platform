# CY 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `b0d34938`；CY installation `917cd341-96a5-4428-9508-03c716c587ad` /
  generation `a2fdbdb1-430c-417b-969d-6bd30874d38c`，binding rev6/epoch3
  enabled/ready，九路 rev276/group303，attempt=0；唯一外置 Runtime Host PID 39950
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 CX installation `2e374e12-7523-466d-aed7-bdabe8b69aff` rev214
  disabled/hash `sha256:74a1bb4d5f9790c1aa09eccadf7735ff5ec7828c4b61b112a7466acadb7c5d6c`；
  recovery rev70/hash `sha256:46c6ad1eb001f60bbbb6028920be8457b5d99911d56e5e05411b11fd6cc3e068`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CY 正式退休与 CZ direct successor。不使用定时 wake。
  本波无页面改动，不开自控浏览器。退休 preflight 前不得创建 `replacement-cz`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CY、CX definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 39950 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CX rev214/recovery70 执行 transfer -> CY rev215 disabled、
   renew -> recovery71 / definition rev216 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev217 disabled；落 verification、测试、
   精确提交；自动进入 CY 正式退休与 CZ direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
