# AR2-7D ReviewAdvanceHostService（ACCEPT）

基线 `w1-aip@d5912501`。生产 registry 仍会因 content 缺项 fail-closed。本切片只补齐 `ecommerce_growth_review_advance` 的命名 HostService：接受包合同 `review_handoff.advance` 的 **ACCEPT**，回读 Occurrence/Case 及四 Artifact 绑定，提交 `ReviewDecisionReceipt`（含 Handoff/Task/Brief 精确引用）。`RETURN` 未接线前 fail-closed。不 push，不前推 `AOS-000571`，不宣称整波 7D GREEN。

## 文件

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_review_advance_host.py`

## 行为

- 命令包络与包内 `ReviewHandoffRequest.command_payload` 一致，另带 `requestHash`；hash 覆盖去掉 `requestHash` 后的正文。
- ACCEPT 必须带四族 Artifact、内部 content Handoff 槽位和中文业务 TaskSpec；禁止租户覆盖键与未知字段。
- execute 由 `_review_lineage` 取得已存在的 Handoff/Task/Brief 精确引用（不发明 Provider 调用或外部副作用）；`sideEffects.externalEffectsAllowed` 恒为 false。
- `verify_receipt` 原样回读；adapter 目标 Receipt 仅为 `receiptRef`。
