# 评估通过后的人工阶段决定

2026-09-11，基线9d89d2f9，AOS-000573。231-5要求画像/诊断/方案各阶段exact review后才下一阶段。现有BusinessInvestigationEvalCoordinator通过仅返回request-human-stage-decision；ReviewIssue负责失败问题解决，不应为人工通过伪造违规问题。最终GrowthPlan审批和内容handoff已有独立路径，也不替代画像/诊断的阶段许可。

## 权威与边界

新增领域StageDecisionRevision，明确当前tenant、TaskRun、Plan精确版本、StepRunAttempt、阶段、分析对象精确版本、原Artifact、EvalReport、责任计划及人工负责人。人工决定accept/return/reject/revoke，reason必填；accept带明确有效期（最多7天，沿用首链handoff边界），其余不得携带有效期。修订需priorRef及CAS，旧accept不能跨revision/attempt/对象hash沿用。模型不能生成这份决定；正式入口必须从已认证服务端身份和当前ResponsibilityPlan human_principal槽解析actor。

分两步施工：本波新增 `services/aos-api/aos_api/ecommerce_analyst_stage_decision.py` 严格契约和纯适用性检查，不存储/不授权运行；下一波补领域Owner/不可变修订与Receipt/RLS、当前责任人读取、评估/原Artifact/检查点核验，再接阶段worker和产品入口。技术方案承认当前未有可用阶段决定Owner，不用客户端引用自证授权。

契约固定三阶段portrait/diagnosis/solution-design，分别绑定InsightRevision/DecisionSummaryRevision/GrowthPlanRevision。须携带同一TaskRun的EvalStageAttemptRef，约定仅在边界将solution-design映射为Eval的solution_design。适用性函数仅比较已Owner核验的决定与实际传入stage/run/plan/step/subject/artifact/eval/责任计划和now；accept、未过期、当前版本由后续Owner负责，不产生新许可。

验证正向及各引用漂移、跨租户、过期、未来、非accept、自动代理冒充human、错误阶段、非规范身份、旧hash/错误priorRef。无迁移/主库写入/Provider调用/push。最终业务八场景仍待真实执行。
