# AR2-7D Review Task/Brief 权威验证

日期：2026-09-09。基线 `m1@a0153331`；方案为 `ar2-7d-review-task-brief-authority-plan.md`。

## 结果

- 生产 `ReviewAdvanceHostService._review_lineage()` 已从固定拒绝推进为同一 HostTransaction 内创建真实 `public.aip_task` 与 `public.aip_task_brief_*` Owner；Handoff 子回执、Task 和 Brief 使用稳定命名 key，并由最终 Review 不可变回执一并承载。
- Task 创建后从 `public.aip_task` 回读完整创建正文、version 与 request hash；Brief 从 `public.aip_task_brief_head`、`public.aip_task_brief_revision`、`public.aip_production_contract_receipt` 回读，并按 Owner 原算法重算 request/content/result-ref 摘要。
- `taskSpec` 只接受精确字段集、四族 canonical Artifact 顺序、相同 GrowthPlan/Artifact exact refs 和规范中文业务文本；嵌套 `revision=true`、隐藏格式字符、技术任务文字、未知字段及 lineage 漂移 fail-closed。
- 所有 Store commit 均由 `TransactionBoundConnectFactory` 吞掉；真实 PG 验证外层 rollback 后 Task/Brief 均为零。无 Provider 调用、TaskRun、Approval、外部发布或外部业务写入。

## Red / 修正

1. 旧生产方法固定抛出 `review ACCEPT requires existing Handoff, Task and Brief authority`，证明原 Host 仅能依赖测试替身。
2. 初次 PG 实现暴露测试命令缺外层 ref，并确认漂移由 `AipTaskIdempotencyConflict` fail-closed；按真实合同修正。
3. 独立复核发现嵌套 bool/int 弱相等、Task 正文未全量回读、Brief 未直接确认 public Owner；补严格 DTO、public 四表回读和原始 JSON 摘要重算。
4. 篡改测试最初直接传 dict，PG 驱动拒绝适配；改用 `Jsonb`。尝试直接改 Brief 原表时数据库权限已拒绝，该非产品失败未用于宣称覆盖；最终以只读 public 原行摘要复核覆盖运行路径，并用可更新的 Task 原文 `revision: 1 -> true` 反例证明类型漂移被拒绝。

## Green

- 专项：Review Host + 真实 Task/Brief PG，`13 passed, 7 warnings in 4.00s`。
- 扩大回归：Review/Handoff/Content 邻接、Workshop business Task、ContentCampaign workflow、ProductionContract Store、runtime registry，`55 passed, 7 warnings in 3.46s`；日志 `/tmp/ar2-review-task-brief-regression-final2.log`。
- `py_compile`：实现与两个测试文件通过。
- AR2-1 closure：`scanned=1707`、`classified=91`、`migrated=57`，五类错误数组均为空。
- memory validate：`AOS-000571`、`GREEN`、Delivery Receipt 865、Event 2226、Task Receipt 846；未前推权威。
- 独立只读终审：三轮收紧后无本切片剩余阻断；实现 SHA-256 `ba0954d395e915a09a16dcec6a2b55cac125a5aa545aac2c8e985d6b8af11f5e`。

## 文件摘要

- `ecommerce_growth_runtime_adapters.py`：`ba0954d395e915a09a16dcec6a2b55cac125a5aa545aac2c8e985d6b8af11f5e`
- `test_ecommerce_review_advance_host.py`：`1a43a96297097db12344a6302dd01c60732ca5d334eecda62727349548481614`
- `test_ecommerce_review_task_brief_authority_pg.py`：`49e9f592818605102360f6dd8fd8e2534cbda263c3be645849c9256a3d29ae7a`
- 方案：`3bae8aaca078c7995678fd350657e5d9a02c4b6e7fbfbadb3739988aa18030b7`

## 边界与下一步

本切片只闭合 Review 输出侧 Task/Brief 权威。GrowthPlan 当前性、ReviewIssue、EvalReport、四 Artifact 与 AnalysisReceipt 的实际 Owner exact 回读尚未全部闭合，`ecommerce_growth_review_advance` 继续不加入 `RUNTIME_WIRING_PROVEN_OPERATIONS`。下一切片按 231-6 补这些输入权威；230 L0 继续挂起。
