# AR2-7D Analysis RECONCILE_UNKNOWN Host 同事务组合验证

日期：2026-09-09
基线：`m1@cae6118c`
结论：`AR2_7D_ANALYSIS_RECONCILE_HOST_COMPOSITION_GREEN`

## Rules 与验证结论

- 以 closure manifest、动态阶段验证器、231-6 N4 和施工卡为权威；m1 单人串行、最小变更、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- `runtime.analysis.reconcile_unknown` 现在只把 prior UNKNOWN Run 原子推进到 RECONCILING，并保存 incomplete 统一 Receipt；不重放原命令、不调用 Provider、不推进 Plan/TaskRun、不声称目标结果已解析。
- 首次执行与 replay 均回读 prior Analysis Receipt、immutable Run、UNKNOWN predecessor、领域 transition Receipt 和统一 Receipt；任一 tenant、hash、lineage、target、dispatch 漂移均失败关闭。
- 迁移 `ar2_012` 将既有 SECURITY DEFINER 函数的 search path 固定为 `pg_catalog, public, pg_temp`，临时同名表不能遮蔽 public 权威；upgrade/downgrade 均已实际验证。

## 实现与一致性

- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：组合 `BusinessInvestigationReconciliationCoordinator` 与统一 Receipt Store，首次写入同一 HostTransaction；重放不再次调用 coordinator。
- `services/aos-api/aos_api/ecommerce_business_investigation_run.py`：增加历史 state exact read 和 begin_reconcile Receipt 严格回读；SQL 显式限定 public；兼容范围仅限历史 `createdAt` 等价拼写与 `priorRef.receiptId=null` 省略，其余 raw/DTO 必须 canonical 等值。
- `services/aos-api/alembic/versions/ar2_012_ecommerce_analysis_reconcile_search_path.py`：线性接续 `ar2_011`，只修改函数配置，不改表和业务状态。
- 方案边界保持一致：没有 target Receipt Owner，因此本切片停在 RECONCILING；后续终态解析另行施工。

## 测试证据

- PostgreSQL migration/同事务专项：`7 passed`。覆盖 ar2_012 upgrade/downgrade、TEMP shadow、首次推进、稳定重放、跨租户、target hash 漂移、raw nested ref 空白漂移和外层回滚。
- 主机编排与领域 Saga：`35 passed`。
- registry/store/HTTP dispatch/package/host-port/review-handoff 邻接：`70 passed`。
- 完整 `tests/extension_runtime`（未开启 PostgreSQL opt-in）：`740 passed, 471 skipped`。
- Python compile、`git diff --check`：通过。
- Closure：`1707 scanned / 91 classified / 57 migrated`；`hashErrors`、正反向未分类依赖、跨层 import、动态引用错误均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。

## Red/修复轨迹

- 原测试先证明 RECONCILE 被 Host 拒绝；接线后转为 RECONCILING 合同。
- 组合夹具依次暴露 case/profile 形状、历史时间拼写和测试块位置问题，均在测试范围内修正。
- TEMP shadow 首次触发 `Run expected version conflict`，定位为旧 SECURITY DEFINER 函数隐式优先搜索 pg_temp；以 ar2_012 最小迁移修复后通过。
- 独立复审发现 legacy raw 校验放宽会吞掉嵌套 exact ref 空白；收窄到两个已知历史序列化差异并增加反例后，复审确认 blocker 关闭、无剩余 blocker/major。
- 两轮未携带专用 DSN 的测试误连 5433，以及一次并行 migration 引发共享角色更新竞争，均为无效环境运行；固定 18434 且串行后全部通过，未据此修改产品逻辑。

## 内容摘要与保留风险

- Run Store SHA-256：`b5db4b77e058e6195c936d483706353b41c964915884dc2aae04fe72bd3ea03c`
- runtime adapters SHA-256：`f6d043f6528b39c0bf60fab6023cc2b3f371705dd20a5334e9e24415cb8bc159`
- ar2_012 migration SHA-256：`8494ac546cf4053405ce0404d738017b02378731fede34df774b79b359d36f66`
- `RuntimeCommandReceipt` 仍没有统一可读 Owner；当前 target 绑定采用 receipt id/request hash 的 fail-closed 约束，合法但不匹配的未来 Producer 会被拒绝而不会误推进。
- 本结论不解除 runtime readiness seal，不授权真实源读取、Provider、生产迁移、真实外部动作、dispatch 切换或发布。
