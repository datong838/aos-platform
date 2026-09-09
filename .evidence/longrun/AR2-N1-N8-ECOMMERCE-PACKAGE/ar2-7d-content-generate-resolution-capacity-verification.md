# AR2-7D Content Generate Resolution / Capacity 验证

- 验证时间：2026-09-09T07:48:59Z
- 基线：`m1@4723dc971c9a87e2f996cde868e2febd31f7da48`
- 方案：`ar2-7d-content-generate-resolution-capacity-plan.md`
- 结论：`AR2_7D_CONTENT_GENERATE_RESOLUTION_CAPACITY_AUTHORITY_GREEN`

## 已证明

- ContentGenerate 在同一事务与同一数据库 cutoff 下只读复验当前单候选 `content_campaign` FAILOVER Route、RegisteredModel、ProviderInstance、RuntimePolicy、Price、Route/Model EvalGate、Provider health、CapacityPool、CapacityReservation 与 RUNNING AgentRun 的 exact lineage。
- Provider health 要求 `observed_at <= cutoff < expires_at`；CapacityReservation 要求 `created_at <= cutoff < expires_at`，未来记录与已过期记录均 fail closed。
- CapacityReservation 命令 ref 固定 revision 1，并由 immutable request hash 绑定 AgentRun、route/model/provider、当前 pool revision 与 token unit；pool 原文、拆列、current head、token 额度和 model context window 均复验。
- Route 固定为单候选 FAILOVER；本切片不宣称或执行 fallback。CapabilityBinding 最新 revision 与 resolution dependency 留在下一切片。
- 无 reserve、consume、release、AgentRun transition、Secret 解析、Provider 调用、费用、生产迁移或外部副作用。

## 验证结果

- 聚焦测试：55 passed；补充隔离 PostgreSQL schema 测试所在文件：22 passed。
- 扩展回归：188 passed，覆盖 ContentGenerate/Review、ModelRuntime contracts/resolver/store、Capacity authority/reservation、AgentRun transition/execution。
- 新增的 PostgreSQL schema 测试通过 pytest 既有自动建库、全量迁移、销毁夹具直接执行组合 Capacity Owner 查询；证明真实表列与 `FOR SHARE OF r,h` 语法兼容，不改共享数据库。
- 当前共享 `aos_test_admin` 的额外只读探测显示尚未安装 `public.aip_model_capacity_reservation`，因此不把该共享库声称为本切片运行态证明；正式验证来自隔离迁移库。
- Python 编译：通过。
- `git diff --check`：通过。
- AR2 closure：`scannedPythonModules=1707`、`classifiedModules=91`、`migratedModules=57`，五类错误数组均为空。
- memory validate：`AOS-000571`、`GREEN`、Delivery Receipt 865、Task Receipt 846、Event 2226。
- 独立只读终审：无剩余 blocker；确认时间漏洞关闭、单候选语义一致且无新增副作用。

## 文件摘要

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：`66ec8b42fd08a8ee2a0da0ed5d947db10ecad807cba61fc124731fc0236d716e`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`：`bb457e620cdd40fca08267092c6dedf7621af065527a8fe2a7f57af49646dd53`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_route_budget_approval_authority.py`：`1a41f757697a9016713fec5fb0bcaad5ea27ebd8c568535c771848824650ca05`
- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_resolution_capacity_authority.py`：`189a045a49a3cff0cde1e7f43037bb9fa1a8f282907d044a16ad21710654f0fb`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7d-content-generate-resolution-capacity-plan.md`：`4d55d2c5ab2f6c51f1a3ebe4ba28f9976388c1f118f4cb577c3ce358fce3032b`

## 保留边界

本结论只证明 Resolution/Capacity 输入权威可在 host revalidation 中 fail closed，不构成完整执行授权。CapabilityBinding、7A receipt-first execute/verify、真实 Provider 调用与任何对外效果继续保持未授权；230 L0 单独授权事项继续挂起。
