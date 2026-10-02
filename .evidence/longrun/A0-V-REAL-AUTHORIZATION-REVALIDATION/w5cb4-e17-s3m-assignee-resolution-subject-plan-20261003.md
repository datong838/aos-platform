# E17-s3m AssigneeResolutionReceipt 职责主题精确绑定：文件级方案

基线 `aos-platform/m1@7d8e88b2`、Authority `AOS-001183`，Task `W5CB4-E17-S3M-ASSIGNEE-RESOLUTION-SUBJECT-EXACTNESS-20261003`。先读231/231-9 首链、原 `AipAssigneeResolutionStore.resolve`、`AipProductionContractStore._require_exact_assignee_resolution` 和 Analyst Stage Review 原真实 Store 隔离测试。真实库 `a0v_135` 只读、Host/worker/Provider关。

## 缺口与最小点

`resolve` 把 `request.subject_id` 持久写入 Receipt，并把它纳入 snapshot hash；Plan 消费时检查租户、Receipt 状态、快照存在、有效期、选中 assignee 精确版本及 required capability 覆盖，但 SELECT 未取 `subject_id`，也未与当前 `slot_id` 比较。一个未过期、同人同能力的 Receipt 理论上可跨职责 slot 复用。231-9 要求审批、任务与产物绑定 exact 输入；这种跨职责复用不能当成合法职责授权。当前有相同主题 `analyst.portrait.review` 和 `content.review` 的原正向夹具。

相邻回归发现旧 `test_w2b_production_contract_store.py` 夹具把 Receipt subject 写作 `responsibility-plan:w2b/slot:content.review/<随机值>`。工作台上位合同 115 的正式观测 subject 是 `responsibility-plan:{planId}@{revision}/slot:{slotId}`，而旧夹具既无 revision、又带不属于 slot 的后缀，不能拿它证明当前 Plan 接受任意 subject 属于产品合同。此波消费门只接受与槽位 ID 完全相同的现有正式 Plan 创建正向输入；纠正这个旧夹具的生成 subject 为 `content.review`，保留同一 Provider/Binding/Capability 正向断言。任务级完整 `planId@revision/slotId` 校验由既有 Task Cockpit 独立执行；本波不声称已实现它。

1. 在 `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py` 的 `disposable_database()`、org-org/dev-project 创建原 `analyst.portrait.review` 真实 human membership 与原 `resolve` Receipt，然后故意用于另一个 slot ID、相同人和空 required capability。先运行旧码 RED；若 RED 成立，同一 `create_responsibility_plan` 前置依赖门应直接拒绝 `ASSIGNEE_RESOLUTION_SUBJECT_DRIFTED`，创建 Receipt0、Plan head计数不动、无需走到 freeze。此既有专用夹具明确只允许 org-org，不能在它上面假造 dev-org canary；租户隔离用原通用测试独立复核。
2. 若 RED，生产只在 `services/aos-api/aos_api/aip_production_contract_store.py:_require_exact_assignee_resolution` 原 SELECT 增 `subject_id`，要求它精确等于 `slot_id`，不改生产者、snapshot 算法、既有同主题正向、其他 assignee 分支或 DB schema。错误用明确 `ASSIGNEE_RESOLUTION_SUBJECT_DRIFTED` 包装为原 `ASSIGNEE_RESOLUTION_INVALID` blocker。
3. 新负例、原 Analyst 正向、`test_w6_01_exact_assignee_resolution.py` 与相关 Plan/Binding 相邻回归；纠正上述旧测试夹具后复验其 Provider 正向仍成立；方案/代码复审、静态检查，必要时浏览器只读验禁入。Receipt 的其他存量风险（当前成员撤销、Binding 版本变化、DB 角色可插入 Receipt）单独报告，不在此最小波假称解决。未知效果只读对账，不能将测试夹具或页面200计为首链。
