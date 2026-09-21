# CR 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `24b8fac0`；CR installation `913cb7a1-4912-471a-abbf-452e3ce999a9` /
  generation `a4a16448-5581-4948-b962-777ff601e855`，binding rev6/epoch3
  enabled/ready，九路 rev255/group282，attempt=0；唯一外置 Runtime Host PID 12390
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- CQ 未执行 transfer。definition 仍为 CP installation
  `1d8b71c5-1cde-4d16-b16f-835f92bf8663` rev193 disabled/hash
  `sha256:e1bee2c59d4803a5e996fd125a51ef1534853b5478af3b56b667513592320cf9`；recovery
  rev63/hash `sha256:785823471c14d9eda4e67250e19f9b498116aaf510e62a77ff47d0275dfa24e6`。
  本波按 AX 先例从该仍冻结的 CP 边界转入 CR，不复活 CQ generation。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CR 正式退休与 CS direct successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CR、CP definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 12390 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CP rev193/recovery63 执行 transfer -> CR rev194 disabled、
   renew -> recovery64 / definition rev195 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev196 disabled；落 verification、测试、
   精确提交；自动进入 CR 正式退休与 CS direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。
