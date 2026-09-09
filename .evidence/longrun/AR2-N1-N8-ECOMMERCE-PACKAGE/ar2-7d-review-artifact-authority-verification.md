# AR2-7D Review 四 Artifact 权威验证

日期：2026-09-09。基线 `m1@2e9827d9`；方案 `ar2-7d-review-artifact-authority-plan.md`。

## 结果

- Review revalidate 从 `public.aip_artifact` 一次回读四个 package Artifact，逐项要求 `portrait/diagnosis/growth_plan/evidence_summary` 与真实 `artifact_type` 一一对应。
- `ArtifactRevision` 的适配 revision 明确取真实 `family_revision`；standalone Artifact 固定为 revision 1。命令 id/revision/hash 必须与 append-only Owner 行完全一致。
- 四个 Artifact 必须来自同一严格非空、无首尾空白的 AIP TaskRun；当前 ReviewIssue/Eval subject id/hash 必须命中这四项之一。
- 查询限定 `public` schema；TEMP 同名表、负租户、缺项、family/hash/revision、混合/空白 TaskRun 与 subject 漂移均 fail-closed，PG 种子由外层事务回滚。

## Red / 修正

1. 原 Review Host 只检查四个调用方 ref 的顺序与互异性，未读取 Artifact Owner。
2. 首版加入 public exact 回读、family、revision、同一 TaskRun 和 subject 集合约束。
3. 独立复核发现数据库外键不排除空字符串 run id；收紧为严格字符串、非空且 trim 前后一致，并增加不同 run、空串和首尾空白反例。
4. 终审确认有限适配切片无剩余 blocker。

## 验证

- 专项：Review Host + Artifact PG，`16 passed, 7 warnings in 3.33s`。
- 扩大回归：Review Host、Task/Brief、GrowthPlan、Issue/Eval、Artifact、Review Command、Eval Runner、Review Return，`40 passed, 7 warnings in 4.95s`；日志 `/tmp/ar2-review-artifact-regression.log`。
- `py_compile` 与 `git diff --check` 通过。
- AR2-1 closure：1707 scanned、91 classified、57 migrated，五类错误数组全空。
- memory validate：`AOS-000571` / `GREEN`，Delivery Receipt 865、Event 2226、Task Receipt 846。
- 独立只读终审：run id 阻断关闭，无剩余 blocker；runtime adapter SHA-256 `0850ccf3fee2fc5904ce8b5c76b78712a2a464b1b34ed40fab740446fc70bd17`。

## 文件摘要

- `ecommerce_growth_runtime_adapters.py`：`0850ccf3fee2fc5904ce8b5c76b78712a2a464b1b34ed40fab740446fc70bd17`
- `test_ecommerce_review_advance_host.py`：`e478451ea6600fe5fd47ef575ecc46aa7f17bc7b26b9a3fd52d3487bda88b4a1`
- `test_ecommerce_review_artifact_authority_pg.py`：`40ba749762cc424863b536c0fc0afde748afb4adbc93650b9323c3800c5295ff`
- 方案：`dfce4f0514998d28d231210866f27761c13baef8fc809975ee35c6720d0b762e`

## 边界与下一步

family→artifact_type 是本切片冻结的 package-to-L0 有限适配规则；未证明现有 BusinessInvestigation typed Artifact 发布链会生成这些字面类型，也不表示媒体 Artifact family selection/master/variant 已批准。AnalysisReceipt、Plan/Run 与 compilation TaskRun 的真实连接仍待闭合，Review 不加入 readiness seal；无 Provider、TaskRun 创建、Approval、发布或外部业务写入。下一切片继续 AnalysisReceipt/Plan/Run exact lineage，230 L0 挂起。
