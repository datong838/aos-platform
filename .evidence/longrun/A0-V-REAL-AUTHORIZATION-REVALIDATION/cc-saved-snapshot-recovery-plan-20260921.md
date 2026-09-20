# CC 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `ec90af79`；CC installation `03942567-0f78-4530-b9dd-634bec59c780` /
  generation `c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2`，binding rev6/epoch3 enabled/ready，
  九路 rev210/group237，attempt=0；唯一外置 Runtime Host PID 38020 保持在线。
- definition rev151 disabled/hash
  `sha256:f32d555f0fab51da085050993c07d36f786be867f7ef25d2f7fd32ebaa6d905a`；recovery
  rev49/hash `sha256:6a5673ae858453ca9a525d0759bf29b63c681f9f07eb1aa07d347fd7d116bf5b`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0、
  canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CC、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 38020 不动，启动受控纯 HTTP API；读回 Cron=false、snapshot
   worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、controls 后关闭 API。
3. **冻结输入转移**：从 CB rev151/recovery49 执行 transfer -> CC rev152 disabled、renew -> recovery50 /
   definition rev153 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev154 disabled；落 verification、测试、精确提交；
   自动进入 CC 正式退休与 CD direct successor。

## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、不动其他分支，
230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
