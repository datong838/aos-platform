# AS 取消失败边界与正式续继方案

## 事实边界

AS installation `5d0a6d5a-4024-430f-831b-2af15b5ca889`、generation
`4cc2dc84-a452-4bac-aa56-0b1519a9826a` 已通过 20 次 Host 续租观察，并将冻结组
`c5ff1926-45b0-56de-b6b3-07d5b7d053a1` 转移到 definition rev69、recovery rev22。
受控 18181 profile 同时包含独立 snapshot worker；definition 启用后它自然领取 attempt
`af7c1fc1-8283-40d7-ab62-f7d6145417c6`。临时 API 停止后该 attempt 以 revision5、
`RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict` 终结。

只读对账确认：attempt 仅一笔；十二 Run 仍 running，十二 Dataset Receipt、一个 relationship、一个
1168-link command 保持；retirement、原幂等键 Store Receipt、`ecom_link`、link Outbox、projection pending
均为零，`dev-org/dev-project` canary 为零。该失败不授权重发。

## 文件级清单

1. `scripts/a0v_as_attempt_guard.py`：固定 attempt、请求摘要、definition/recovery、十二 Run 与 Store 零副作用边界，
   只读输出 `FAILED_FREEZE_BOUNDARY`，任何漂移 fail-closed。
2. `scripts/a0v_as_saved_snapshot_recovery.py`：新增 `pause-failed`，仅在守护边界完全相等时以 CAS 把
   definition rev69 推进到 rev70 disabled；不得执行或重发 attempt。
3. `services/aos-api/tests/extension_runtime/test_a0v_as_attempt_guard.py` 与
   `test_a0v_as_saved_snapshot_recovery.py`：覆盖固定身份、终态原因、零副作用和 rev70 暂停门禁。
4. 本方案完成专项测试、累计相关回归、只读浏览器验收、证据与提交后，进入下一波正式退休 AS。

## 退出与停止条件

- 暂停前必须再次读回唯一 failed attempt、12/12 冻结输入、零 Store 副作用、九路 rev108/group135、
  三资源健康和 canary0；否则不写 definition。
- 暂停只允许生成 rev70 disabled，且使用唯一幂等键
  `a0v-as-saved-snapshot-pause-failed-v1`。
- 暂停后下一波按正式 disable/detach Owner 退休 AS，核对九路回 legacy、资源释放和零 pending；随后才允许
  从 exact detach Receipt 创建 AT direct successor。
- 不调用 `run_definition`，不读取商城源数据，不重发原 Store 幂等键，不 push，230 L0 保持挂起。
