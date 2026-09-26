# W5cal｜自然三阶段运行接线调用图审计（进行中）

本文件是 W5cal 第 1/6 步的中间证据，**不是 verification，不算本波完成**。只读代码/当前 AOS PG，未起 Host、未读商城源、未建 AgentRun、未调用 Provider。

## 已确定的正反事实

- `scripts/a0v_ecommerce_runtime_host.py:_build_business_workers/_serve` 只启动 product-event、analysis-data-requirement、baseline-assessment。全仓 `GrowthPlanTaorWorker`、`DiagnosisTaorWorker`、`PortraitTaorWorker` 的引用只有定义和测试；没有可见生产调用点。
- `ProductEventAnalysisService._initialize` 通过正式 bootstrap 建 Case/Run/Task/Plan/TaskRun；`_BootstrapProductionStartService.start` 明确把首输入 TaskRun pause 且要求 `aip_agent_run` 不存在。DataRequirement 的 `_AnalysisDataResumeSession` 能在原当前来源事务内恢复 TaskRun，但它不是 D01/D02/D03 执行器。
- `ecommerce_growth_runtime_command_receipt` 的 `ecommerce_growth_analysis_advance` 原 Receipt 有 `occurrenceRef`、`runRef`、`taskRunRef`、`compilationRef`、来源截止面与安装代际/epoch；可作为候选反向路由，但每次领取仍须和当前 `extension_operation_dispatch_binding`、原 Occurrence、TaskRun/Plan/Case 与安装版本核验。当前一条原 Receipt 为 `PREPARING/completed=false`，不可视为完成分析。
- 真实 recovery PG `a0v_092`、同租户只读计数：`aip_task_run` 0 running（历史 4 succeeded/1 cancelled）、`aip_agent_run` 0、`ecommerce_analyst_growth_plan_head` 0、四类评审 `aip_artifact` 0。现在没有可合法领取的活跃三阶段任务；旧 pending 事件不能当成新任务重放。
- `AipAgentRunService.create` 是唯一现有建 Run Owner，要求当前 active AgentInstance/SkillBinding、精确 Skill/Logic/ModelRoute/Policy、健康能力；queued→running 还经过模型/Provider/价格/健康及 capacity reservation。手工 pilot 脚本使用固定标识和 `inputRefs=[]`，不能移植为自然执行。D01/02/03 worker 自己已有前驱/attempt lineage 严格门，但没有自动 provisioner。
- 现有 portrait/diagnosis/growth worker 和 snapshot resume 非 PG 邻接测试 **131 passed、9 skipped**；跳过包括显式 disposable DB 图测试，不能称完整自然三阶段 GREEN。第一次测试命令因误写不存在的测试路径未运行，随后纠正并得到上述结果。

## 待完成的精确工程门

先定义一个 Host-owned 领取契约：以当前原 Receipt/TaskRun 为候选，按安装代际与 epoch、当前 AIP composition、唯一 stage/前驱、当前 actor/markings/预算/路由/容量和已存在 AgentRun/attempt Receipt 复核；原始结果 unknown 只能对账，不能新 ID 重发。证据不足时只读/拒绝。之后才 RED→最小新 stage worker→Host 接线→隔离 PG 完整图测试。现有 12 Run 退休不是此链的代码前置，但不能用其失败输出满足来源新鲜度。
