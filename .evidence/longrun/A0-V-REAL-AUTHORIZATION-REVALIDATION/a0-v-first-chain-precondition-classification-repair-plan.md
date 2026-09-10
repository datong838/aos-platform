# A0-V 首链前置条件分类修复方案

## 1. 问题

当前 A0-V 采集器把 `ProductionContext`、`ProductionStartDecision`、`TaskBrief` 与 `ResponsibilityPlan`、`StageTemplate` 一并按“集合必须非空”判断。这会产生两类错误：

1. A0-V 明确不执行 A1 真实首链，而 ProductionContext、ProductionStartDecision 和 TaskBrief 都是首链运行期间基于具体 Task/Run/评审结果形成的动态权威；要求它们在 A1 前存在会形成循环依赖。
2. ResponsibilityPlan 与 StageTemplate 是首链静态前置，但任意一条 draft、blocked 或错误 profile 记录也会通过“非空”门，存在假 GREEN。

## 2. 权威依据

- `a0-v-readiness-plan.md` §1：A0-V 只复核首链准入，不执行 A1 真实模型任务。
- `ecommerce_business_investigation_aip_authority.py`：静态物化项是调查 StageTemplate 与 ResponsibilityPlan，且只在 READY 时冻结责任计划。
- `ecommerce_business_investigation_aip_composition.py`：运行期组合要求唯一 frozen 调查 StageTemplate、唯一 frozen `ecommerce.business-investigation.readonly` ResponsibilityPlan；ProductionContext 只有拿到具体 run 的 exact ref 后才可解析。
- 231-6：评审 ACCEPT 才创建内部 Task/TaskBrief；ProductionStartDecision 是生产启动动作的结果，不是 A1 前置配置。

## 3. 最小改动

- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`；
- 扩充 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`；
- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`；
- 重采结果并新增验证记录。

不修改业务 API、数据库、租户配置或运行开关。

## 4. 判定规则

1. `productionContexts`、`productionStartDecisions`、`taskBriefs` 继续 GET 并校验响应结构、租户声明和 canary 隔离；空集合记录为可观察事实，不产生“缺前置” blocker。
2. StageTemplate 必须唯一匹配 `profile=ecommerce.business-investigation`，其 lifecycle/readiness 分别为 `frozen/ready`，blockers 为空，seal 字段完整，阶段 ID 按顺序精确为 `portrait`、`diagnosis`、`solution-design`。
3. ResponsibilityPlan 必须唯一匹配 `profile=ecommerce.business-investigation.readonly`，其 lifecycle/readiness/coverage 分别为 `frozen/ready/complete`，blockers 与 uncoveredSlots 为空，并精确包含六个非重复职责槽位。
4. 任何列表正文畸形、count 与 items 数量不一致或静态前置多义均失败关闭。
5. 动态实例即使存在也不据此宣告 A0-V 或 A1 GREEN；A1 将以具体 occurrence/run/task 的 exact refs 单独验收。

## 5. 验证与退出

专项 fixture 覆盖：精确静态前置通过、draft/blocked/错误 profile/重复候选/错误阶段/槽位不足失败、三类动态集合为空不阻断、畸形集合失败关闭。恢复环境复采应移除三个循环依赖 blocker，同时以精确原因保留 StageTemplate 与 ResponsibilityPlan 缺口。

退出标记：`A0V_FIRST_CHAIN_PRECONDITION_CLASSIFICATION_GREEN`。该标记只代表 A0-V 前置分类与判定可靠，不代表真实配置已补齐。
