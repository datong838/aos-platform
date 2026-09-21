# CV 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `a7978ef7`；CV installation `f94149ca-a01e-4a20-836f-3f5132e0dbb7` /
  generation `82aec2b8-072d-4f2e-9624-f9539c8890a6`，binding rev6/epoch3
  enabled/ready，九路 rev267/group294，attempt=0；唯一外置 Runtime Host PID 27622
  保持在线。configuration rev1 已引用 RuntimePolicy rev11。
- definition 为 CU installation `2c2d5506-1f80-4557-bf4b-00ead0258002` rev205
  disabled/hash `sha256:b341ed9ef3772e4990f9631820897e7623f65099a3d795d35fa13ad58d7a2525`；
  recovery rev67/hash `sha256:7dcfc71097e84bc4b25529a1c70a98904768ea1655b037bb777c24cae51ab3b9`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。
- 上一成功 attempt 终态为 **rev5**；guard overlay 仍需 predecessor_view revision=4。
  本波仍属 BG-00。封板后自动进入 CV 正式退休与 CW direct successor。不使用定时 wake。
  本波无页面改动，不开自控浏览器。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CV、CU definition/recovery、attempt=0、零副作用与唯一 Host。
2. **纯 HTTP 18181**：保持 PID 27622 不动；check/serve 读回 Cron=false、snapshot
   worker=false、进程内 Host=false；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CU rev205/recovery67 执行 transfer -> CV rev206 disabled、
   renew -> recovery68 / definition rev207 enabled，全部 `sourceReads=0`。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal。
6. **终态/verification/commit**：stop-only 推进 rev208 disabled；落 verification、测试、
   精确提交；自动进入 CV 正式退休与 CW direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源
读取、负租户写、业务副作用、未知提交或手工执行时 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起。不使用定时 wake。
