# E17 当前正式配置来源：文件级计划（进行中）

基线：`aos-platform/m1@dc59eea3`，AOS-001160。复习 231 总计划 A1、231-2 签名发行、231-3 配置与启用状态机，以及 D-waves 2026-10-01 BG00gw 第 142 项。当前权威库只读；本计划不授权写入、Host 启动或业务验收。

## 已核代码边界

- `aos_api/extension_runtime/runtime_configuration_candidates.py` 只计八类当前 head/revision；`all_present` 仅表示各类非零，不能证明同一相容链。
- `aos_api/extension_runtime/configuration_source_catalog.py` 只列当前 frozen 职责计划与 active、未 kill 的运行策略候选；不承诺当前签名来源或六类依赖相容。
- `aos_api/aip_runtime_configuration_sources.py` 的 `assemble_current_configuration` 从角色/策略精确引用读取，沿运行策略重验数据、出站、网络、配额、预算策略和预算修订；这是配置组装的原权威读者。
- `aos_api/aip_production_contract_store.py` 的职责计划原生产者与 `aip_responsibility_template_authority.py` 的已安装签名模板读者是两段独立边界。前者的冻结记录不单独证明当前 Growth 1.13 正式发布、同代安装和批准 actor。
- 当前 `scripts/a0v_current_preview_http.py::serve_limited` 在 OIDC 后仍调用四旧包、零 binding 的预览子进程；`scripts/a0v_ecommerce_runtime_host.py` 仍以 `FORMAL_OWNER_AUTHORITY_UNPROVEN` 关闭。不得用配置记录绕过这两门。

## 下一个可执行 RED 和最小实现边界

只读定位发现当前 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.13.0/content/responsibility-templates/business-investigation.readonly.json` 已有同一 BI 模板，且隔离签名安装用例通过原 Registry/安装链；但 `ApprovedBIPreparationResolver._installation_rows` SQL 固定 `version.version='1.12.0'`。因此 1.13 即便有精确签名和获批安装，也无法进入原 BI Plan 准备入口。这是独立于外部 OIDC 的代码缺口。

1. 先修改 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：沿现有 1.13 原 Registry/签名/获批安装正链，调用原 `ApprovedBIPreparationResolver.select`，要求返回该安装及精确签名模板引用；同一测试在选择 1.12 时保留旧版正例。先跑 1.13 RED，禁止测试绕过原读者直接查表。
2. 最小实现只改 `services/aos-api/aos_api/aip_responsibility_template_authority.py` 的 `_installation_rows` 精确版本集合：允许 `1.12.0` 与 `1.13.0`，不接受其他版本。原唯一匹配、exact lock、签名、字节和信任根复验保持原样。不能把本地签名 Receipt 升格当前正式来源。
3. 已有 `current_configuration_sources_case.py::test_runtime_policy_fails_closed_when_any_dependency_head_drifts` 覆盖六类错代，`configuration_stage_consumer.py` 已调用精确组装；不重复测试或改动这些路径。版本扩展后跑相邻 BI 读者、1.13 安装、1.12 兼容及候选包测试。
4. 复核当前库/页面仍禁入、方案与代码一致、无新外部效果后，落 verification，更新 D-waves、01/06 与 Prime 权威并精确提交。正式 actor/OIDC、当前发布和六类配置仍是独立待办。

本计划没有代码 GREEN 或当前正向配置证据；E17 正式 OIDC、独立身份、信任根、Growth 1.13 release、八类相容来源、assignment/Owner 和自然首链仍待证。
