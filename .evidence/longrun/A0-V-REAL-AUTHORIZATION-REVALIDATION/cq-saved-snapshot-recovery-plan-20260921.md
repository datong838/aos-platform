# CQ 保存快照恢复与单一自然 attempt 方案（2026-09-21）

## 1. 当前权威

- HEAD `91649633`；CQ installation `fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80` /
  generation `ae8a1005-99fb-48c5-9dfe-8f76590bc0c8`，binding rev6/epoch3 enabled/ready，
  九路 rev252/group279，attempt=0；唯一外置 Runtime Host PID 8784 保持在线。
- definition rev193 disabled/hash
  `sha256:e1bee2c59d4803a5e996fd125a51ef1534853b5478af3b56b667513592320cf9`；recovery
  rev63/hash `sha256:785823471c14d9eda4e67250e19f9b498116aaf510e62a77ff47d0275dfa24e6`。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
  projection pending=0、canary=0。本波只转移既有冻结输入，不读取商城源数据，不调用
  `run_definition`。
- 上一 attempt 终态为 **rev4**；guard overlay 仍需 predecessor_view revision=4，以适配
  共享 CB classify。pause 后 live definition 为 disabled，classify 叠加
  `definitionState=enabled`。本波仍属 BG-00 生命周期实证。封板后自动进入 CQ 正式退休与 CR
  direct successor。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定 CQ、definition/recovery、attempt=0、零副作用与唯一 Host 在线边界。
2. **纯 HTTP 18181 并存**：保持 PID 8784 不动，启动受控纯 HTTP API；读回 Cron=false、
   snapshot worker=false、进程内 Host=false，第二 Host=0；完成 prepare、schedule-ingest、
   controls 后关闭 API。
3. **冻结输入转移**：从 CP rev193/recovery63 执行 transfer -> CQ rev194 disabled、renew ->
   recovery64 / definition rev195 enabled，全部读回 `sourceReads=0`；未知结果只对账，不重发。
4. **唯一自然 worker**：固定 Lease、guard、worker、supervisor；仅启动一个自然 worker，禁止手工执行。
5. **连续观察**：50 秒只读采样至唯一 attempt 正式 terminal；仅 deadline 情形进入 1800 秒同 attempt 预算。
6. **终态/verification/commit**：正式终态后 stop-only 推进 rev196 disabled；落 verification、测试、
   精确提交；自动进入 CQ 正式退休与 CR direct successor。

## 4. 本波当前阻塞与恢复子流程

2026-09-21T12:01Z `prepare` 被 `PermissionError: budget policy is not effective` fail-closed。
权威预算策略 `a0v-ecommerce-budget-policy-v1` rev10 的 `effective_until` 为
`2026-09-21T11:55:25.232326Z`，已过期；CQ Host PID 8784 仍在、未 transfer。
按 BR/AW 既有路径恢复，禁止绕过策略或改表：

1. 新建 CQ 专属私有 journal，使用已评审 `text-readiness-v2` 三个公共合成文本案例；先做零调用
   preflight，每例最多一次 Provider 调用，失败/未知保留 intent 且停止。
2. 三例通过后，用 `a0v_formal_text_model_renewal.py` 冻结续期计划，再以同一 planHash 经
   Budget/Policy/Model/Route Owner 和原 CAS/EvalGate apply；apply 阶段 ProviderCalls=0。
3. 因 CQ configuration rev1 仍精确引用 RuntimePolicy rev10，发布 rev11 后必须走既有同
   installation/generation configuration refresh：新 configuration rev2 → configure/enable。
   九路继续绑定 CQ exact identity `252/279` epoch3，claim/running/unknown/attempt 均为零。
   禁止直接改 binding/route，禁止复用 CQ 首次 configure/enable 幂等键，也禁止续接唯一的
   J `extension_dispatch_configuration_refresh_receipt`（与 AW 同一硬门）。
4. 刷新后重试尚未写入的 `prepare`；未知提交只读查回，不重发。若 prepare 仍因九路 epoch
   拒绝，冻结实际边界并转入 CQ 正式退休与 CR successor，不扩 Owner、不改触发器。

已完成第 1–3 步。configuration successor `85103076-e401-4624-8141-4dc8374db731` rev2 hash
`sha256:4fd728d8652c1be02b8300865283839c1cb4d86f0f2b6e120685a45c82fb632a`，policyRef 已是
RuntimePolicy rev11；configure `3bc3460e-1b76-4aae-96f9-d23204b86a57` 与 enable
`1f330063-94a2-44a2-96a8-b7a858d67480` 均 succeeded；Binding rev9/epoch5 enabled/ready，
九路仍为 epoch3 rev252/group279，attempt=0。

2026-09-21T12:11Z 重试 `prepare` 在任何结果文件写入前被
`ValueError: current J binding differs` fail-closed：`a0v_snapshot_current_controls.py`
要求 Binding rev6/epoch3，与刷新后的 rev9/epoch5 不兼容。这与 AW 停止门相同。本波不再
启动 worker、不创建 attempt、不走 J dispatch refresh。下一波：CQ 正式 blocked retirement
与 CR direct successor；CR 必须用 current policy 全新 configure，使 snapshot prepare 仍落在
rev6/epoch3。

已完成第 1–2 步：journal `cq-text-governance-renewal`，三例
`FIXED_TEXT_CASES_PASSED`（ProviderCalls=3），planHash
`57bdebd9dec1405691d1d1f331cf49a24efcbd1a1c3a933dc86f05ba7b8423bf`，BudgetPolicy/
RuntimePolicy rev11（有效至 `2026-09-22T12:05:24.269764Z`），Model/Route rev10，
apply ProviderCalls=0。Host PID 8784 保持在线。当前待第 3 步 configuration refresh。


## 3. 停止条件

任一 identity/Receipt/hash/revision/Run/route 漂移，出现第二 Host/worker/attempt、商城源读取、
负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发；不 push、
不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
