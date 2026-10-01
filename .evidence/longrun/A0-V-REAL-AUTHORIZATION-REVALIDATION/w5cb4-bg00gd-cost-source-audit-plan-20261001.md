# BG00GD 首链费用来源与部署缺口审计计划

基线AOS-001044/a500e728/a0v127，7强一致CURRENT；复习231-5与437。此波为只读代码/配置审计及既有门回归，不新增业务代码、迁移、生产写入或Provider调用。RED/实现不适用，不用重复一套模拟producer冒充正式来源。

## 核验范围
1. BudgetCost提议/批准/消费Receipt→BudgetRevision既有链；核对后续ModelPriceSnapshotRevision/BudgetPolicyRevision要求。
2. AipModelRuntimeStore.publish_price_snapshot/_publish/_validate_dependencies、AipModelGovernancePolicyStore.publish_budget/require_model_dependencies及contracts：是否已有从已消费批准派生的正式producer，不能仅以路由存在作结论。
3. 已有budget_cost_runtime gate、ModelPrice/Policy当前head/窗口/Provider/同approval绑定及测试证据性质；记录fixture人工插入、legacy opt-in不能充正式生产来源。
4. 仅检查.env中配置键是否有值/路径存在，不打印凭证；这不是进程有效配置或合法UID证明。
5. 复跑标准独立测试库的预算政策发布拒绝、开发授权/绑定及费用消费回归；禁旧AOS_EXTENSION_PG_TEST=1。

## 产出与下一最小路线
verification含文件/命令/结果/风险/下一文件级施工路线。缺失正式producer须先精确方案和RED：从已消费费用批准/Receipt/当前budget/provider解析固定授权，派生匹配price与budget-policy；独立权限、幂等、撤销竞争和查询恢复。不得移除现有active直接发布禁门或用管理员插入替代。
