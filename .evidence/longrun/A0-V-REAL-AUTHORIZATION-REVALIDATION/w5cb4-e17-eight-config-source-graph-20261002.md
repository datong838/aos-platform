# E17 八类配置原来源只读对账（2026-10-02）

基线：`aos-platform/m1@98a663fd`，`AOS-001156`。本波只读仓库及当日重启证据；未写当前库、未启 Host/worker/Provider，也没有读取商城源。当前库 `aos_current_preview_20260927@a0v_135` 的八类候选均为 0、binding/assignment/identity 均为 0，证据见 `w5cb4-daily20261002-latest-753-restart-verification.md`。本清单是合法来源追踪，不是配置批准或运行授权。

## 原生产入口与严格候选

| 类别 | 当前候选判据 | 原生产入口与权限/审批边界 |
| --- | --- | --- |
| 职责计划 | `aip_responsibility_plan_head` 当前修订 `frozen` | `aip_production_contract_store.py:create/revise/freeze_responsibility_plan`，`routers/aip_production_contracts.py`；须真实职责与当前 actor，不因创建草稿就计入。 |
| 运行策略 | `aip_runtime_policy_head` 当前修订 `active` 且 `killSwitchEnabled=false` | `aip_model_runtime_store.py`，`routers/aip_model_runtime.py:publish_policy`；正文须精确引用网络、出站、数据、配额、预算策略。 |
| 数据分类 | guard policy 当前修订 `active`、当前有效期 | `aip_runtime_guard_policy_store.py`，`routers/aip_runtime_guard_policies.py:publish_data_classification`；R2 激活审批另证。 |
| 出站策略 | guard policy 当前修订 `active`、当前有效期 | 同一 store 与 `publish_egress`；R2 激活审批另证。 |
| 网络策略 | network policy 当前修订 `active`、当前有效期 | `aip_network_policy_store.py`，`publish_network` 与 activation proposal/decision；须当前出站策略及正式批准。 |
| 模型配额 | governance policy kind `quota` 当前修订 `active`、当前有效期 | `aip_model_governance_policy_store.py`，`routers/aip_model_governance_policies.py:publish_quota`；R2 激活审批另证。 |
| 预算策略 | governance policy kind `budget` 当前修订 `active`、当前有效期 | 同一 store 与 `publish_budget`；引用当前预算修订，R3 批准另证。 |
| 预算修订 | `aip_budget_head` 当前修订 `active`、当前有效期 | `aip_budget_store.py`，`routers/aip_budgets.py`；普通 `POST /budgets` 明确拒绝 active，须正式预算激活审批链。 |

精确计数见 `extension_runtime/runtime_configuration_candidates.py`。这些是**租户候选**，不是已绑定该安装的配置。`extension_runtime/configuration_source_catalog.py` 只供选择 frozen 职责与 active 运行策略；`aip_runtime_configuration_sources.py:assemble_current_configuration` 从运行策略沿网络→出站、数据、配额、预算策略→预算修订逐个锁定原 head、核 exact ref/hash/生效期，再形成四来源配置文档；`configuration_stage_consumer.py` 仅在正式 Host 授权和原事务内提交。八个独立正数仍不能证明引用彼此相容，更不能证明配置已提交、binding enabled 或首链可运行。

## 下一安全施工项

1. 当前实例：正式 OIDC、独立 API/Directory/Runtime/Web 身份、当前 signed Growth1.13 release/trust、精确 assignment/Owner 未齐；不得用 test-only 身份或直接插表使八计数变正。待正式材料到位后，按原路由与审批产品顺序建立相容的当前来源，再走 runtime-apply/verify→配置→enable；每步只读回执对账，未知结果不重发。
2. 独立代码波：按 D-waves 已登记 `d2b3c4f`，以 `ecommerce_analyst_stage_review_command.py` 原 Decision/Run/Eval/Artifact 生产路径和现有 Review Receipt 读者为起点；先复习 G2 正式 Eval 来源，在可销毁 PG 对**原服务**持久 Receipt→Handoff/Task/v3 Brief/单原 Artifact 做缺失/错租户/过期 RED。若 G2 原生产条件仍缺，只做能独立失败封闭的读者切片，不借 fixture 宣称首链。

复核命令：`rg -n 'aip_.*_head|lifecycle|effective_from' services/aos-api/aos_api/extension_runtime/runtime_configuration_candidates.py`；`rg -n 'def publish_|def freeze_responsibility_plan' services/aos-api/aos_api/routers/aip_{production_contracts,model_runtime,runtime_guard_policies,model_governance_policies,budgets}.py`；`rg -n 'assemble_current_configuration|_load_runtime_policy|_load_network_policy|_load_governance_policy' services/aos-api/aos_api/aip_runtime_configuration_sources.py`。
