# GW-b-2c2c1b3c2d2b3b2｜生成宿主 Review Receipt v3 独立读者

基线 `AOS-001128` / `m1 b7b7b23b`，延续 231-5 §9、栖月汇统一 Task/Handoff 和 BG00GW。新 accepted-stage Review Receipt 形状与 hash 已定义，但 Host execute 不持久化，生成宿主 `_review_receipt` 仍只接受旧 ReviewIssue/四 Artifact。因此本轮只建立读取原持久化 Receipt 的严格新分支合同；正式执行禁入保持。

文件：`services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 的 `_CONTENT_REVIEW_RECEIPT_FIELDS`/`ContentGenerateHostService._review_receipt`；`services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py` 先 RED。新分支调用方必须带 `source_kind=accepted-stage-v1` 与**独立原 Owner expected `source_lineage`**，不得从 Receipt 自身或 Task/Brief 拿作 expected；读者同租户读取唯一 Receipt 行、核 17 字段、request/body/target hash、Handoff/Task/Brief/GrowthPlan、同一单原 Artifact、decision/sideEffects/replayed。旧默认保持四源合同。

本切片使用有界事务替身对 persisted row 的 shape/hash 做正反测试，同时保留未来原 store PG 正向为下一门，不把替身当正式验收。下一步将原 StageDecision/Eval/permission/撤销/期限 Owner 生成 expected，在同一事务调用该读者和 v3 Task/Brief 读者，再接可读 Artifact/人工评审。Host execute/Provider 在全消费者齐备前保持禁入，当前真实库只读，不读商城源/旧Run/手工Run/dev-org写，不 push。
