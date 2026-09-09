# AR2-7D Content Generate Handoff / Task / Brief 输入权威验证

日期：2026-09-09。基线 `m1@674e3f91`；方案 `ar2-7d-content-generate-handoff-lineage-plan.md`。

## 结果

- 新增未完成的 `ContentGenerateHostService.revalidate` 前半段；严格接受 package `ContentCapabilityRequest.command_payload()` 的固定字段、十二类 authority refs、四 Artifact、1～200 个 fact refs、CNY 与整数费用/token 上界，拒绝布尔冒充整数和请求摘要漂移。
- 从 `public.ecommerce_growth_runtime_command_receipt` 唯一回读 ReviewDecisionReceipt，重算正文摘要，严格核对 response/target receipt ref 的字段、整数 revision、receiptId、request hash、ACCEPT、零外部副作用及 Handoff/Task/Brief/GrowthPlan/四 Artifact。
- 共享锁定 public Task 与 TaskBrief head；按 Review Owner 算法重算 Task request、Brief request/content hash，并要求输入 Brief exact hash、current draft、创建 Receipt、Handoff/GrowthPlan/Artifact 闭包和 `externalPublicationRequested=false` 全部一致。
- 当前批准 GrowthPlan 继续复用已验证 Owner 规则。四 Artifact 通过重新验真的 immutable ReviewDecisionReceipt 回链其 Review 时完成的 Owner 校验；本切片没有冒称再次读取 Artifact Owner。

## Red / 修正

1. 基线只有 ContentGenerate adapter spec，不存在 production HostService。
2. 初版 strict 输入与 Review/Task/Brief 回链通过后，独立复核发现遗漏输入 Brief hash 对账，且 Review/Brief receipt refs 仍可能受 `true == 1` 弱相等影响。
3. 补入输入 Brief prefixed hash、Review ref StrictInt/canonical raw 校验、Brief Owner result ref 字段/类型/原始 JSON 摘要校验，并严格检查 sideEffects 类型。
4. 方案把 Artifact 描述收紧为 immutable Review Receipt 回链，不再声称本切片二次读取 Owner。
5. 终审确认两个 blocker 全部关闭，无剩余 blocker。

## 验证

- 专项：确定性输入 authority + 隔离 PG，`15 passed`（扩大命令前为 11，最终含新增弱类型反例）。
- 扩大回归：Content Generate 输入两文件 + 全部 `test_ecommerce_review_*.py`，`66 passed, 7 warnings in 3.58s`。
- `py_compile` 与 `git diff --check` 通过。
- PG：Review Host 创建真实 Task/Brief；public 限定不受 TEMP 同名 Task 影响，负租户拒绝，外层 rollback 后 Task/Brief 均为零。
- AR2-1 closure：1707 scanned、91 classified、57 migrated，五类错误数组全空。
- memory validate：`AOS-000571` / `GREEN`，Delivery Receipt 865、Event 2226、Task Receipt 846。
- 独立只读终审：无剩余 blocker；实现 SHA-256 `2b983739afd6d4f66180ead1e32e7eb95eb0b5c67c6a1504a1a0f2521ee44c92`。

## 文件摘要

- `ecommerce_growth_runtime_adapters.py`：`2b983739afd6d4f66180ead1e32e7eb95eb0b5c67c6a1504a1a0f2521ee44c92`
- `test_ecommerce_content_generate_handoff_lineage.py`：`f3063fd771392b5459f556d059f3a3d5551e3cc2417ce0e3fd8d4b0bd84770f1`
- `test_ecommerce_content_generate_handoff_lineage_pg.py`：`c1f7cc0dfd1696cd81519c990c9c85a4c40685b2b92c5261e64829ef902ee988`
- 方案：`ad2cebc73ffad150601a8a93b68165c5af0bd0b9dba8ff46ca67232a84b6f0cf`

## 边界与下一步

该类目前只有输入 revalidate，尚未具备 execute/verify_receipt，不能通过 runtime registry 的完整服务形状，更未加入 readiness seal。下一切片继续 AgentInstance/Responsibility/Capability/ModelRoute/Pricing/Approval/Budget/Capacity 当前权威；随后才能连接 7A Receipt-first 状态机。未解析 Secret、未调用 Provider、未创建输出 Artifact、未产生外部写入；230 L0 挂起。
