# AR2-7D Analysis RECONCILE_UNKNOWN Host 同事务组合施工卡

日期：2026-09-09
基线：`m1@cae6118c`；方案：`docs/m1@c7ab816`
状态：专项验证完成，不解除 runtime readiness seal

## Rules 与问题

- m1 独占串行；复核 231-6 N4、包内 `analysis_runtime.py`、既有 prior Receipt 校验与 `BusinessInvestigationReconciliationCoordinator` 后编码；最小改动、隔离 PostgreSQL、自测与只读复审、证据后精确提交；不 push，230 L0 挂起。
- UNKNOWN 命令只允许围绕 prior `AnalysisRuntimeReceipt.targetReceiptRef` 中固定的 `RuntimeCommandReceipt` 对账。不得重发原命令、创建替代 Run/Plan/TaskRun、切换 Provider 或把 Receipt 不存在解释为失败／成功。
- 现有领域 Run Owner 只表达 `UNKNOWN -> RECONCILING`，没有“目标结果已解析”的终态写入口；因此本切片只接通可证明的 RECONCILING，不伪造 RUNNING 或完成。

## 实现范围

1. 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：从 prior Receipt 的 immutable Run/target lineage 回读当前 Run State；要求当前状态为 UNKNOWN，或为同一历史 UNKNOWN 的 RECONCILING replay；`uncertainCommand.commandId/requestHash` 必须分别绑定 target Receipt 的 `resourceId/contentHash`，operation 必须仍在领域协调器 allowlist。
2. 最小修改 `services/aos-api/aos_api/ecommerce_business_investigation_run.py`：增加历史 Run State exact read 与 `begin_reconcile` transition Receipt 严格回读；仅兼容 BIW4 历史 `createdAt` 时区等价拼写及 `priorRef.receiptId=null` 的省略写法，其余 raw/DTO 必须 canonical 等值；显式限定 public schema，重算 requestHash 和状态 contentHash，不改变状态机或数据库结构。
3. 新增线性迁移 `services/aos-api/alembic/versions/ar2_012_ecommerce_analysis_reconcile_search_path.py`：仅把既有 `ecommerce_investigation_run_state_transition_biw4_007` 的函数级 search path 固定为 `pg_catalog,public,pg_temp`，使临时同名表不能遮蔽 public Run authority；降级恢复原函数配置，不改表或业务状态。
4. 首次执行在同一 `HostTransaction` 内调用既有 `BusinessInvestigationReconciliationCoordinator.begin_reconcile`，保存新的 incomplete `AnalysisRuntimeReceipt`：phase=`RECONCILING`、action=`RECONCILE_RECEIPT`、target 不变，其他 Run/Compilation/Plan/TaskRun lineage 保持 prior exact 值，所有数据恢复字段为空。
5. 重放与 `verify_receipt` 必须同时回读统一 Receipt 和领域 `begin_reconcile` transition Receipt，核对 UNKNOWN predecessor、RECONCILING successor、target uncertain command 与完整响应正文；任一漂移返回拒绝。
6. 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_analysis_advance_host.py`、领域 Run 测试并增加隔离 PostgreSQL 组合测试，覆盖首次推进、稳定重放、目标／Run state／transition Receipt 漂移、TEMP shadow、跨租户与外层回滚；包合同继续证明不重发原命令。

## 退出条件与保留边界

- Analysis Host 专项、领域 reconcile Saga/Run 状态机、runtime Store、registry/Router 邻接和专用 PostgreSQL 通过；Python compile、diff check、closure、memory validate 通过；独立只读复审无 blocker。
- 本切片不增加目标 Receipt 查询适配器或解析终态，因为当前权威未定义 `RuntimeCommandReceipt` 的统一可读 Owner；目标仍未解析时保持 RECONCILING。后续须补明确的 target Receipt Owner/解析状态后才能收敛 RUNNING。
- 不读取真实源、不调用 Provider、不执行真实外部动作、不迁移共享／生产库、不切换 dispatch、不发布；`completed=false`，230 L0 继续挂起。
