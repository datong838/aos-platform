# BG00HA 原 D01 自然调度施工前置核对

基线 AOS-001081 / `m1@a7c91ec5`；Task `W5CB4-BG00HA-D01-NATURAL-DISPATCH-20261002`。依据 231-5、231-9、BG00GZ、D-waves Subject 清单。此文记录原调用链与文件级 RED，未启 Host/worker/Provider，也未迁移或写当前真实库。

## 1. 原链已有部分与未接部分

- `ecommerce_growth_runtime_adapters.py:AnalysisAdvanceHostService` 在原 Host 事务准备 Analysis TaskRun/Receipt；它不在事务内运行 Provider。
- `ecommerce_analyst_d01_atomic.py:NaturalD01AtomicCoordinator` 已用原 `AnalysisContinuationOrigin`、`D01SourceSelectionStore.read_current`、`NaturalD01Issuer` 和 `AipAgentRunService._create_in_transaction` 同事务创建**queued AgentRun**，保留稳定 key/原 Receipt。文件注释也明确未注册；全仓调用检索没有生产调用者。
- `ecommerce_analyst_{portrait,diagnosis,growth_plan}_worker.py` 均已用原 `CanonicalTaorRunner`，但三 worker 没有生产构造点；`Portrait/Diagnosis/GrowthPlanGenerationCommand` 仅在相邻测试中构造。`main.py` 的内容 worker 启动模式提供了现存默认关闭、Host 活跃、独立 runtime 身份、失效停止边界，不能把 Host adapter 的 DB 事务当生成 worker。
- D01 `PortraitGenerationCommand` 必须带原 AgentRun version、稳定 attempt、budget Ref、capacity Reservation Ref、批准的 D01 SourcePacket。queued AgentRun 自身不含预算/容量预留；当前 D01 原链也没有等价于内容链 `ContentCapacityOwner` / `ContentBudgetCommandOwner` 的生产者。缺此两项时不可从来源包臆造 Ref，也不可把内容链的别的 Run 预算挪用。

## 2. 精确施工顺序

1. 先核原 AIP 预算/容量 Owner 能否为 D01 AgentRun + 固定 attempt 建独立预留，冻结额度、Price、批准与 idempotency key；若需新增意图或 SQL 权限，另列 additive migration，不直接写当前库。
2. 受限来源组合从原 Analysis Receipt、批准 D01 SourceSelection、queued AgentRun、预算和容量 Receipt 派生 `PortraitGenerationCommand`。`read_portrait_input_packet` 再验当前引用与 markings；未知预留结果先查原 key，绝不重建 AgentRun/重新发 Provider。
3. 从原 Task/Runtime Host 生命周期启动默认关闭的 D01 worker；只在当前正式 Host assignment/独立 runtime 身份、安装 generation/epoch/config fence 齐备时可领原 Task。事务外调用现有 `PortraitTaorWorker`，其成功 StepRun/Checkpoint/observe 回读后才交 BG00HB EvalRun Owner。D02/D03 依相同规则串行接续，不用 D01 成功掩盖后段缺口。

拟涉及代码目录：`services/aos-api/aos_api/ecommerce_analyst_d01_atomic.py` 原 Owner 复用；`aip_budget_reservation_*` 与容量 Owner 的原路径需先核主体类型；新 D01 组合文件仅承载必要来源读取/调度；`main.py` 仅在完整 worker ready 后加默认关闭启动入口。测试位于 `services/aos-api/tests/` 与 `tests/extension_runtime/`，优先隔离 PG 原 Owner、当前身份和真实 SQL，禁止只以 mock 的页面/Provider 结果作验收。

## 3. RED 与门限

RED：原 Analysis Receipt/批准选择/AgentRun/TaskRun 不一致、预算或容量缺失/过期/跨租户、安装代次漂移、Provider unknown 后重入、Host 中途失活、旧 Plan、非 D01 Skill、重复 key、StepRun 无观察，均不得调用原生成 executor。正向需从原 Analysis Receipt 产出合法 queued AgentRun、独立预算容量 Receipt、同一 D01 命令及原 TAOR Step 成功；先隔离验证，再凭当前正式身份决定是否真实启用。

本波先完成前置核对；当前缺 D01 预算/容量生产 Owner，不能安全进入 worker 最小实现。Goal 仍可推进独立 GT-a Model 评测用途代码及 D01 费用 Owner 设计；此处未宣布整体 blocked。原 Subject writer/Stage consumer 与自然首链仍 pending。
