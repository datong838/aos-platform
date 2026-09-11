# 经营参谋阶段决定合同包化方案

日期：2026-09-12

基线：`c37d5acc`

状态：实施完成，宿主当前决定端口待办

## 目标

把 exact 人工阶段决定的领域 DTO 与无权威适用性比较迁入 growth 包。阶段固定为 portrait、
diagnosis、solution-design，分别绑定 InsightRevision、DecisionSummaryRevision、GrowthPlanRevision；
只有 accept 且在不超过七天的显式有效期内，才能供后继内部 Handoff 检查。

## 边界

- 包内复制公开值合同 `EvalStageAttemptRef`、`AssigneeRef/AssigneeKind`，保持宿主 JSON Schema；
  不导入 `aos_api`。
- reviewer 必须是与 createdBy 相同的 `human_principal`；stage attempt 必须绑定同一 TaskRun 和
  exact step，solution-design 仅兼容既有 `solution_design` Eval 边界写法。
- plan、subject、Artifact、EvalReport、ResponsibilityPlan 的类型与 revision 必须严格；布尔值
  不得冒充 revision/attempt/version。
- 适用性函数接收 TenantContext 只做相等比较，不能据此授权；决定必须先由宿主当前 Owner 读取。
- 当前性、人工身份、角色、租户、Eval/运行/责任计划读取、发布事务均留宿主。
- 不修改宿主生产文件、Candidate、OCI、Registry、Installation 或 operation。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_decision.py` | `2682979a24abeaba6625f983599eeb4e6a2064723a45476a0f50ea9594e1aaf4` | 验证输入；宿主兼容文件不改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_decision.py` | new | 包内 DTO 与纯适用性比较 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_decision_package.py` | new | schema/行为 parity、负向、隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `1d31704f36d09e49f5d58585171f8d993ad544163f6a47d136bee34075081e8f` | 登记 9.12 切片 |

## 退出与下一门

全 DTO schema parity、合法/过期/替换/非人工/布尔版本行为、宿主回归、独立 import、编译和
AR2-7 closure 全绿后提交。下一波拆阶段决定 Store/评审 authority 的宿主只读端口边界，或继续
迁移下一纯规则；29 项整体仍保持 PENDING。
