# AR2-7D Analysis RESUME_DATA Host 同事务组合验证

日期：2026-09-09
基线：`m1@542e74c2`；方案：`docs/m1@c7ab816`
结论：`AR2_7D_ANALYSIS_RESUME_HOST_COMPOSITION_GREEN`

## Rules 与范围

- m1 独占串行、方案先行、最小改动、隔离 PostgreSQL、证据后精确提交；不 push。
- 仅开放 `runtime.analysis.resume_data` 的 no-effect 恢复组合；`RECONCILE_UNKNOWN`、230 L0、真实 Provider、真实源、生产迁移、外部发布继续关闭。
- Evidence 结果是对持久 EvidenceBundle 及其 public immutable Evidence 重算后的 Saga DTO 适配，不声明存在独立持久 EvidenceBuildReceipt。

## 实现与一致性

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`
  - exact 回读 prior Run/Compilation/Plan/TaskRun/Checkpoint、DataRequirement、Fulfillment、Mapping、Hydration、Readiness、EvidenceBundle 与原始 Evidence；不采信命令中的 ready/covered 声明。
  - Hydration 先按 Mapping exact ref 与 Fulfillment 输出的 resourceType/resourceId/revision/contentHash 四字段筛选，`receiptId:null` 与省略 null 不再造成漏配；匹配集仍保持 200 上限和唯一性拒绝。
  - 同一 HostTransaction 内依次调用 Run `resume_after_data`、AIP `resume_run`、统一 AnalysisRuntimeReceipt；重放从三份持久 authority 复核，不重复推进。
  - verify 分开核验不可变 RunRecord 与 RunState successor/priorRef，避免混用版本轴。
- `business_investigation_mapping.py` 增加 public-qualified exact read，并逐列、原始 JSON、tenant、hash、status 对账。
- `aip_business_investigation_compile_saga.py`、`aip_production_contract_store.py` 将本链 exact/revoke/Evidence 查询锁定到 public，关闭 TEMP shadow。
- JSON 对账采用 canonical hash；严格区分布尔值与整数。

## 验证结果

- 相关 Owner、Host、Store 与隔离 PostgreSQL组合：`95 passed`。
- 修复两项复审 blocker 后聚焦回归：`43 passed`。
- extension runtime 标准套件：`737 passed, 471 skipped`。
- 隔离 PostgreSQL 三 Owner 核心：首次提交后各一份 Run successor、AIP resume control Receipt、统一 runtime Receipt；新连接重放数量不增长；统一 Receipt 失败时前两项整体回滚；Checkpoint 数量为零。
- Hydration 真实 Owner 写入回归：持久 `outputRefs[].receiptId=null` 时四字段 exact 查询仍唯一命中。
- Alembic：`ar2_011 (head)`；Python compile 与 `git diff --check` 通过。
- 一次误将全 extension runtime 与 dedicated opt-in 同时开启，旧测试固定连接已停止的 18432，结果为 `33 failed, 375 errors`；属于测试环境调用错误。移除 opt-in 后标准套件全绿，上述数字不作为代码结果。

## 独立只读复审

- 首轮发现 Evidence 自证、prior lineage、TEMP shadow、JSON bool/int 和真实事务验证缺口，均已修正。
- 次轮发现全租户 Hydration 201 条扫描，已改为 exact SQL 预筛选。
- 终轮发现 RunRecord/RunState 混用及 `receiptId:null` 漏配，已修正并增加真实 Owner 回归。
- 最终复审：无剩余代码 blocker。非阻断边界是三 Owner PostgreSQL 测试覆盖组合核心而非完整 Host E2E；该限制已如实保留。

## 文件 SHA-256

- `ecommerce_growth_runtime_adapters.py`: `a0e1d0c95d32b046dd29895d667f7f46608d52fad4346bb565a065b79b0391ae`
- `business_investigation_mapping.py`: `7a0f09dd5470cd7783384417a6ff68c66a6d6d7ecc7d67620a9b0ea84dd3782f`
- `aip_business_investigation_compile_saga.py`: `775b8d5618b643126e2fc99bba953225c111d8e7923ec3b3de65bbc6d1b60eb9`
- `aip_production_contract_store.py`: `9cad74452c5853aeeb75eb82d48aabd700f5280c4b86a1e545c1c4bd6c23414e`
- `test_ecommerce_analysis_advance_host.py`: `842613e385d0671b5b6b32c5807db0cd2529fd4d97993fc5f42a22b06f2f5b4b`
- `test_ecommerce_analysis_run_resume_pg.py`: `779b8fde5d7caa1c66e36b260926d58cb5d2f194b813c5a62e687c7cf10cdf56`
- `test_business_investigation_mapping_revision.py`: `89f157ee2ef7322c64f9f7cb694e255dedc727a56112f8dd5b7dbe2a2876b4bd`
- `test_business_investigation_semantic_hydration.py`: `d69682dc8fb725d29aa8fa14eb7674bb4e983c8f431aa35c5051d123d3f9dcda`

## 保留边界

- `runtime.analysis.reconcile_unknown` 继续 fail-closed。
- 本切片不解除 AR2 整组 readiness/cutover seal，不产生 Provider、真实源、外部业务、发布或生产迁移副作用。
