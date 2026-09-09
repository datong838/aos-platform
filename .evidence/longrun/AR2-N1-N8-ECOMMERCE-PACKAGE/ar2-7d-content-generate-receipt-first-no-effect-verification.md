# AR2-7D Content Generate Receipt-first 无 Provider 执行验证

- 验证时间：2026-09-09
- 基线：`m1@15a876d8`
- 方案：`ar2-7d-content-generate-receipt-first-no-effect-plan.md`
- 结论：`AR2_7D_CONTENT_GENERATE_RECEIPT_FIRST_NO_EFFECT_GREEN`

## 已证明

- ContentGenerate 的 `revalidate` 完整执行既有 authority 链并按 HostPort 合同返回 `None`；`execute/verify_receipt` 已具备固定 adapter 所需方法形状。
- 首次执行复用 transaction-bound 7A Store，在外层同一事务内形成 CapabilityInvocation `prepared -> failed` 与 BudgetReservation `held -> released`，返回 N7 严格 `FAILED_NO_EFFECT`；领域 Receipt、统一 runtime Receipt 任一回读失败都会使外层事务回滚。
- Provider request/result、Usage、Artifact、实际费用均为空，三桶最终 held/submitted/unknown 占额均为零，五类副作用计数全为零；没有调用 `submit`、Provider、Secret、外部发布或经营写入。
- 相同完整命令从 tenant/public 统一 runtime Receipt 核对 command hash 后，回读 7A Owner 并原样返回首次持久正文；adapter journal 双回放保持 `replayed=false` 的不可变正文，不产生 runtime Receipt 冲突。完整命令或预算子请求漂移均失败关闭。
- 7A Store 的自有表与 authority 表均显式使用白名单 schema，生产默认 `public`；同名 TEMP 表不能截获调用。`get/_view` 回读 invocation 全行，复算 invocation/reservation hash、核状态映射、四个原始 exact ref canonical 等值及 Provider receipt 实体计数。
- 完整 Receipt 和 reservation exact ref 使用 JSON canonical hash 等值，拒绝 `0/false`、`1/true` 等 Python 弱相等；隔离 PostgreSQL 已证明 RELEASED 后篡改 invocation state 或把 reservation task revision 从 `1` 改为 `true` 会被 Owner 回读拒绝。

## 验证结果

- 新专项：10 passed。
- 7A 隔离 PostgreSQL：10 passed，包含真实迁移、三桶、重放、并发、结算邻接、TEMP 影子和 Owner 篡改反例。
- 扩大回归：211 passed、3 skipped，覆盖全部 ContentGenerate authority、N7 capability contract、HostPort、runtime Store/adapter/registry 与 7A contracts。
- Python compile、`git diff --check`：通过。
- AR2 closure：1707/91/57，五类错误数组为空。
- memory validate：`AOS-000571`、`GREEN`、Delivery Receipt 865、Task Receipt 846、Event 2226。
- 独立只读终审：四轮发现并关闭完整 Receipt bool/int、schema 影子、Owner 摘要、完整命令幂等、journal 重放和原始 ref bool 漂移问题；最终无剩余 blocker。

## 文件摘要

- `services/aos-api/aos_api/aip_budget_reservation_store.py`：`07c24fd5d53bdc9c77f8c8b9284452bff8560cbf944e50b8cfc32847f5b6fe69`
- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：`c5a6ec150efcae9a28e8a3fd368d9f698c06753c4b53779135a6bf80119c33be`
- `services/aos-api/tests/aip/test_aip_budget_reservation_pg.py`：`c0c4d5ff771860adfab1bce6dba2c502ae6667231bb7a9c62add4387ee1053cc`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_receipt_first_no_effect.py`：`37247b01c4f997153cdccb4f36fb2139260dea0a276f150936913328952591d3`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`：`f7caec9e7f8bc94d3d61938299c686f7b1c8f717a2faf3077724e0b5afba39d0`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7d-content-generate-receipt-first-no-effect-plan.md`：`6d8770c52c01ad39a805be0ba83321c06bf4151d564ff35c4b357ae35febea5c`

## 保留边界与下一步

本结论只证明无 Provider 条件下的确定性 `FAILED_NO_EFFECT` 路径，不声称生成了内容，也不授权 Provider、Usage 结算、Artifact、发布或经营效果。ContentGenerate 尚未加入生产 readiness seal；下一项按清册进入 ContentReview HostService 的 Artifact/Task/Brief/Issue/ReviewerAuthority 与 7C feedback 同事务接线前置。若缺少可读 Artifact authority，则继续 fail-closed，不伪造成功结果。230 L0 保持挂起。
