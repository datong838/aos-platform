# DB 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `e3a65959`；DB installation `aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8` /
  generation `c1ae6205-0743-483c-82e3-1d1c95b1ab31`，binding rev6/epoch3
  enabled/ready，九路 rev285/group312，attempt=0；唯一外置 Runtime Host PID 48103
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 DA installation `f4fcdf0b-a37b-419c-9de0-14b08cd7320d` rev223
  disabled/hash `sha256:02b21df15a3d68d768bdabdeb61c3a4912138a320dbac1c7374d40453d52990e`；
  recovery rev73/hash `sha256:13d1f720afe37c554549a5c8605448fb3df7a85f519b92fdae367f0653477cdc`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 DB 正式退休与 DC direct successor。不使用定时 wake。
  本波无页面改动，不开自控浏览器。退休 preflight 前不得创建 `replacement-dc`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 DB、DA definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 48103 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 DA rev223/recovery73 执行 transfer -> DB rev224 disabled、
   renew -> recovery74 / definition rev225 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev226 disabled；落 verification、测试、
   精确提交；自动进入 DB 正式退休与 DC direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
