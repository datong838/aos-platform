# E17-s3o-w-ao-b14｜当前八配置与正式身份差距对账

## 方案与文件级读路

- 复习 231、D-wave E17-s3e–s3j 及原 `extension_runtime/runtime_configuration_candidates.py`。八字段为 frozen ResponsibilityPlan、active 无 kill switch RuntimePolicy、当前有效 Data/Egress/Network/Quota/BudgetPolicy/Budget 的**租户候选计数**；源码明确计数不绑定安装、不授权 Host。`configuration_source_catalog.py` 的可选来源只含已绑定安装 generation 下的 Plan/RuntimePolicy，也不能把八计数当运行准入。
- 本波只读当前原卷和 `.env` 变量**名**，不读取凭据内容、商城源或 dev-org 业务数据；不重复此前隔离生产者的 +1 试验。

## 当前实测

- `docker --context colima-aos-extension ps --filter name=aos-a0v-recovery-pg`：原容器 Up、映射 18435；`BEGIN READ ONLY` 在 `aos_current_preview_20260927` 对 `org-org/dev-project` 查询八类 head：ResponsibilityPlan0、RuntimePolicy0、Data/Egress Guard head 无行、Network0、Quota/BudgetPolicy Governance head 无行、Budget0，SQL exit0。所有 head 为0，故候选 reader 按同一租户/原 SQL 必为八类0；未以历史隔离 +1 推断当前有配置。
- 同库 `BEGIN READ ONLY` 查角色：`aos_aip_binding_readiness_reader`、`aos_aip_capability_issuer`、`aos_bi_plan_issuer`、`aos_aip_tool_issuer` 均0，exit0。仓库 `.env` 仅解析 key：正式 `AOS_OIDC_*` 与 `AOS_AIP_BINDING_*` 均0；已有 `AOS_BUNDLE_ROOT`/`AOS_BUNDLE_TRUST_ROOTS_FILE` 两键不能充当这些身份。仓外未查位置不被断言为不存在。
- 已有隔离生产者：E17-s3e Guard Data/Egress、s3f Network、s3g Budget/BudgetPolicy、s3h Quota、s3i RuntimePolicy 均只证明原签名/审批/低权链可让各自候选 +1；s3j 明确 frozen Plan 仍因六 active SkillBinding 缺当前正式 Model/Route/Eval 而禁入。它们未在当前库发行配置、未给当前 Host assignment/Owner。当前原卷依旧只读，Host/worker/Provider关。

## 决定与下一入口

阻断的首个当前环节是正式身份及来源部署，而非候选 SQL 缺一个 +1 测试。下一波对 Reader/Capability issuer 与 BI issuer 的**当前库切换前置**写可验证施工方案：新一致备份/独立完整恢复、角色/私有凭据/租户 RLS、API 配置、零执行窗口、回滚与只读复核；缺外部 OIDC 时仅停正式 API 写入口，继续可独立的数据库侧准备。不能把 test-only 登录/签名内容接到当前实例。ToolDefinition 无正式来源单独门控；六 Binding/八配置/Host/自然首链仍 pending，Goal active、不 push。
