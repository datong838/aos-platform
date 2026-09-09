# AR2-7D Review GrowthPlan 权威验证

日期：2026-09-09。基线 `m1@f21d5ad3`；方案 `ar2-7d-review-growth-plan-authority-plan.md`。

## 结果

- Review revalidate 将包内 `GrowthPlanRevision` exact ref 严格转换为现有 Analyst Owner ref，在同一 HostTransaction 内对 public head 取共享锁，要求命令 revision 正是当前 revision。
- APPROVED 状态、tenant、version、content hash 与 createdBy 均取自 `public.ecommerce_analyst_growth_plan_revision` 原始 payload；publication receipt 通过 revision.receipt_id 回读，并按 Owner 算法重算 `{expectedVersion, revision: raw payload}` 请求摘要，同时核对 resultRef 原始 JSON 摘要与 actor。
- 三张同名临时表存在时仍只读取 public Owner；旧 revision、draft、hash 漂移与 `dev-org/dev-project` canary 均 fail-closed。revision 为不可变表，只锁可变 head，符合运行角色权限。

## Red / 修正

1. 原 Host 仅检查 `resourceType=GrowthPlanRevision`，无真实当前/批准回读。
2. 第一版同时对 head 与不可变 revision `FOR SHARE`，PG 以权限拒绝；修正为只锁可变 head，并只读不可变 revision。
3. 独立复核发现 Store 内部未限定 schema 可被 TEMP 同名表遮蔽，且 contentHash 本身不是完整正文摘要；改为 public 原行和 publication receipt 直接回读，重算 Owner 请求摘要并增加 TEMP 反例。
4. 最终补齐 payload.createdBy、revision.created_by 与 receipt.created_by 三方一致性。

## 验证

- 专项：Review Host + 真实 GrowthPlan PG，`13 passed, 7 warnings in 4.74s`。
- 扩大回归：Review Host、GrowthPlan PG、Task/Brief PG、Analyst Authority Store、GrowthPlan approval、runtime registry，`28 passed, 7 warnings in 3.74s`；日志 `/tmp/ar2-review-growth-plan-regression-final2.log`。
- `py_compile` 通过；`git diff --check` 通过。
- AR2-1 closure：1707 scanned、91 classified、57 migrated，五类错误数组全空。
- memory validate：`AOS-000571` / `GREEN`，Delivery Receipt 865、Event 2226、Task Receipt 846。
- 独立只读终审：public 原文、receipt 摘要和 TEMP 遮蔽阻断关闭；最终实现另补 actor 三方一致。

## 文件摘要

- `ecommerce_growth_runtime_adapters.py`：`3e1ff5433819c955df74f1bfae25711eda9346e7b98bfab1b98a70b63bf7c961`
- `test_ecommerce_review_advance_host.py`：`1a09c263d023f72929390885e084f06616c5ba79e52eab7b245ae9fcc2ba1915`
- `test_ecommerce_review_growth_plan_authority_pg.py`：`5650a8d59602cfa0107e304cf067deb1f219bf76112b1f0e36f6033224d83b03`
- 方案：`7621e5656b66160159ab46647bd76b6d8fb5db3686ee34abd714bb2dbbf385f4`

## 边界与下一步

本切片仅关闭 GrowthPlan 当前批准权威。ReviewIssue、EvalReport、四 Artifact、AnalysisReceipt、Plan/Run exact lineage 仍未全部回读，Review 不加入 readiness seal；无 Provider、TaskRun、Approval、发布或外部业务写入。下一切片继续 ReviewIssue/Eval/Artifact lineage，230 L0 挂起。
