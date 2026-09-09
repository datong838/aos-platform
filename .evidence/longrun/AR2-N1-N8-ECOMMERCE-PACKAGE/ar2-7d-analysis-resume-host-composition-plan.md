# AR2-7D Analysis RESUME_DATA Host 同事务组合施工卡

日期：2026-09-09
基线：`m1@542e74c2`；方案：`docs/m1@c7ab816`
状态：已实现并验证，不解除 runtime readiness seal

## Rules 与交付边界

- m1 独占串行；复核 231-6 与既有 FulfillmentResumeSaga/Run Owner/AIP Task Store 后编码；最小改动、隔离 PostgreSQL、独立只读复审、证据后提交；不 push，230 L0 挂起。
- 只接 `runtime.analysis.resume_data`；`RECONCILE_UNKNOWN` 继续 fail-closed。无 Provider、真实源、生产迁移、外部发布或真实租户写入。
- 首次执行必须在同一 HostTransaction 内完成 exact 数据闭包验证、领域 Run `resume_after_data`、AIP Task/TaskRun `resume_run` 和统一 AnalysisRuntimeReceipt；任一步失败由外层事务整体回滚。
- 数据恢复复用 prior Receipt 的 Run/Compilation/Plan/TaskRun 与最后 exact Checkpoint；响应 Checkpoint 不换 revision，`priorCheckpointRef=null`，`completed=false`。

## 方案与文件

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：
  - 从 canonical Owner 回读 DataRequirement、DataFulfillmentReceipt、SemanticHydrationReceipt、SourceReadinessEnvelope、SourceMappingRevision、一个 EvidenceBundle 及其原始 Evidence、prior Compilation/TaskRun/Checkpoint；命令可附带的 Dataset exact refs 必须属于该 Bundle 和 Fulfillment，禁止相信命令中的 ready/current/fulfilled 声明。
  - DataRequirement authority 本身必须精确绑定 prior Run/Case/Checkpoint；EvidenceBundle 按其不可变 itemRefs 和 public Evidence Owner 重新计算 required facts 的 coverage/freshness/conflict/uncertainty 与 Bundle content hash，再据此构造 Saga 的只读适配 DTO。禁止把 requirement.requiredFacts 直接抄成 coveredFacts，禁止用当前 runtime 字段伪造历史 Evidence Build 成功。
  - 通过 transaction-bound 组合器复用 `BusinessInvestigationFulfillmentResumeSaga`；组合器在 Saga 发起 AIP resume 时，先调用 `BusinessInvestigationRunStore.resume_after_data`，再调用 `AipTaskStore.resume_run`。
  - 首次成功以后从当前 Task/TaskRun/Plan/Checkpoint 重建 runtime binding，写严格 RUNNING AnalysisRuntimeReceipt，TaskRun ref 使用 successor version 与 successor binding hash；重放先读统一 Receipt，再分别核验 Run transition Receipt、AIP resume control Receipt及当前 successor，不重新推进状态。
  - `verify_receipt` 从三个持久 Owner 回读后精确等值，不以传入 Receipt 自证。
- 如既有 Store 缺少只读历史 Receipt 能力，只在对应 `aip_task_store.py` 增加严格 read-only helper；不得新增第二套写入状态机。
- 修改 `services/aos-api/aos_api/business_investigation_mapping.py`，增加 public-qualified exact read，逐列对账原始 authority、tenant、refs/status/hash，JSON 类型必须严格；修改 `aip_business_investigation_compile_saga.py` 与 `aip_production_contract_store.py`，把本链调用的 exact/revoke/Evidence 查询限定到 `public`，关闭 TEMP shadow。
- 所有统一 Receipt、control Receipt 和 raw/DTO 比较使用 canonical JSON/hash 等值并先做严格字段与 bool/int 类型检查；不得依赖 Python `False == 0`。
- 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_analysis_advance_host.py` 并新增必要的隔离 PostgreSQL 组合测试，覆盖首次成功、相同重放、同 key 异参、数据/映射/证据/Checkpoint/Plan 漂移、非 PAUSED、Run 或 AIP 任一步失败整体回滚、跨租户、重启重放与 verify 篡改。

## 退出条件

- RESUME_DATA 的三个持久 Owner 组合核心及新连接重放在隔离 PostgreSQL 通过；数据库中恰有一个 Run successor、一个 AIP resume control Receipt、一个统一 runtime Receipt，失败整体回滚，且无新 Checkpoint。该测试不冒充完整 Host `execute/verify` 端到端；完整命令路径由严格单元组合测试覆盖。
- START、DataFulfill、FulfillmentResumeSaga、Run Owner、AIP Task lifecycle 邻接回归通过；全 extension runtime、Alembic single head、compile/diff、closure、memory validate 通过。
- 独立只读复审 blocker 清零；验证文档明确 `RECONCILE_UNKNOWN` 与整组 readiness/cutover 仍未完成。
