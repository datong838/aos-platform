# AL 预算窗口失败边界与暂停验证（2026-09-18）

## Rules

- m1 单写者串行推进，不 push；230 L0 保持挂起。
- 先确认失败原点与未知提交边界，再做最小状态变更。
- 不手工调用 `run_definition`，不重发未知结果，不把测试通过当作经营闭环完成。
- `org-org/dev-project` 是正向租户；`dev-org/dev-project` 仅作为零越权 canary。

## 第 1/6 步：失败原点

AL `recoverable_store` attempt `3e319ca5-9e8d-4b0e-a034-295cd3e5b645` 在 revision 382 进入 `failed`，完成时间为 `2026-09-18T11:21:54.803374Z`。对应预算治理策略 `a0v-ecommerce-budget-policy-v1@7` 的有效期止于 `2026-09-18T11:21:54.706218Z`；worker 报错原点为 `_load_governance_policy` 的 `PermissionError`。失败发生在预算策略到期后约 97ms。

## 第 2/6 步：未知提交边界

失败前已形成且仅形成一笔不可变 link command：

- command hash：`sha256:f16b566f1974831e0c662ea67049c77acc1febd12c7bd8ff98e9651d0d396970`
- assessment hash：`sha256:bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b`
- link count：1168
- idempotency key：`snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b`

Store 边界核对为：`ecom_ingest_receipt=0`、`ecom_link=0`、authoritative link outbox `=0`、projection pending `=0`。因此失败位于 link command 持久化之后、Store 批次提交之前；不存在未知 Store 提交，也没有可猜测或可重发的副作用。

## 第 3/6 步：精确暂停实现

`scripts/a0v_al_saved_snapshot_recovery.py` 新增 `pause-failed` 动作。它只接受下列完整事实同时成立：AL attempt 为 revision 382 failed、无 running attempt、十二 Run 仍为 running 且未停止、保存输入和 16 次 recovery 均存在、十二 dataset receipts 与唯一 relationship/link command 精确匹配、Store 三项为零、binding/resource 状态保持原值、预算策略 rev7 已到期、`dev-org` canary 为零。

守卫通过后，脚本以 definition rev50 的 CAS ref 执行正式 `disable`，幂等键为 `a0v-al-saved-snapshot-pause-failed-v1`。

## 第 4/6 步：执行结果

`pause-failed` 返回 `AL_SAVED_SNAPSHOT_FAILED_RECOVERY_PAUSED`，全部 19 项精确事实匹配。definition 从 rev50 enabled 迁移为 rev51 disabled，content hash 为 `sha256:616e3db63a37a0867c7377877efe80c323a4387777646cd06716640eb0300495`。

随后 `inspect` 返回：

- `configurationState=disabled`
- `executionAuthorized=false`
- `routingStatus=disabled`
- `definitionRef.revision=51`
- `sourceReads=0`

AL 不再产生新 attempt，已有十二 Run 和已保存输入保持原状，未扩大任何外部副作用。

## 第 5/6 步：专项验证

- `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_al_saved_snapshot_recovery.py`：1 passed。
- `services/aos-api/.venv/bin/python -m py_compile scripts/a0v_al_saved_snapshot_recovery.py`：通过。
- `git diff --check`：通过。

## 第 6/6 步：结论与下一波

AL 已按正式控制面安全暂停，失败原点和零 Store 提交边界均已闭合。该结果只证明可恢复输入仍完整且旧执行已停止授权，不代表十二 Run 已完成，也不代表真实经营闭环完成。

下一波直接进入 AM 正式接续：用 `text-readiness-v2` 做三次公开合成探针，形成新的治理策略有效窗；随后按 retire/direct successor 路径迁移 AL 的保存输入、十二 Run 与资源所有权，并在新 installation/generation 下恢复唯一执行。AM 成功后才进入经营参谋自然首链。
