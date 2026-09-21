# CF 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `f04990a0`；CF installation `8cf0c597-cf81-4fa5-b1ff-f27e3537a94c` /
  generation `88996259-ad79-4aa6-962c-c29a24559db8`，binding rev6/epoch3 enabled/ready，
  九路 rev219/group246，attempt=0；唯一外置 Runtime Host PID 73889 保持在线。
- definition rev160 disabled/hash
  `sha256:92f0f0b16bde8eb7da3602672c7d8bd032a41664ec4ea8f8bb61cc952de7996f`；recovery
  rev52/hash `sha256:77be40f32ad75219d8b763b1c1b07c06867989a5783a92dd516bd44361d44ffd`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0、
  canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用 `run_definition`。
- 本波仍属 BG-00 生命周期实证，不宣称黄埔 0 期经营首链完成。封板后自动进入 CF 正式退休与 CG successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CF、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 73889 不动，启动受控纯 HTTP API；读回 Cron=false、snapshot
   worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CE rev160/recovery52 执行 transfer -> CF rev161 disabled、renew -> recovery53 /
   definition rev162 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev163 disabled；落 verification、测试、精确提交；
   自动进入 CF 正式退休与 CG direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、不动其他分支，
230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
