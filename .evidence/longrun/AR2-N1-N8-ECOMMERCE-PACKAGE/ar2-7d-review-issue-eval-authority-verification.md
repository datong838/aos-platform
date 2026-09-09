# AR2-7D ReviewIssue / EvalReport 权威验证

日期：2026-09-09。基线 `m1@371dd7a0`；方案 `ar2-7d-review-issue-eval-authority-plan.md`。

## 结果

- Review revalidate 在同一 HostTransaction 中从 `public.aip_review_issue` 读取并共享锁定当前行，将 canonical ReviewIssue 完整正文冻结成 `ReviewIssueRevision` exact ref，只接受当前 OPEN version。
- `public.aip_eval_report_revision` 按命令 exact ref 直接回读；运行时按 Owner 算法重算报告摘要，并复用既有 Review 校验要求 Issue→EvalReport→subject Artifact 与 investigation stage 完全一致。
- Issue 的 `ruleRef/location/evidenceRefs` 及 Eval 的全部 JSON 列先保留原始 JSON 类型，再与 canonical DTO 正文作摘要等价校验；`revision: 1→true`、`passed: true→1` 不能再被 DTO 归一化掩盖。
- 查询全部限定 `public` schema；同名 TEMP 表、负租户、命令 hash 篡改、Issue 关闭/版本前移、subject Artifact 断链均 fail-closed。PG 种子写入由外层事务回滚。

## Red / 修正

1. 原 Review Host 仅验证 occurrence、Case 与 GrowthPlan，未回读 ReviewIssue 或 EvalReport。
2. 第一版 DTO 校验和 Owner hash 重算通过，但独立复核发现先 DTO 后 hash 会吞并 JSON bool/int 类型漂移。
3. 修正为 Issue raw JSON 与 canonical Issue 正文双向摘要一致，并用 raw 正文绑定 exact digest；Eval 全部 JSON 原列与 canonical report 正文一致后，再对 raw report 正文重算持久摘要。
4. 新增两类保持旧摘要不变的类型漂移反例及 subject Artifact 断链反例，终审确认无剩余 blocker。

## 验证

- 专项：Review Host + Issue/Eval PG，`16 passed, 7 warnings in 3.41s`。
- 扩大回归：Review Host、Task/Brief、GrowthPlan、Issue/Eval、Review Command、Eval Runner、Review Return，`36 passed, 7 warnings in 4.39s`；日志 `/tmp/ar2-review-issue-eval-regression.log`。
- `py_compile` 与 `git diff --check` 通过。
- AR2-1 closure：1707 scanned、91 classified、57 migrated，五类错误数组全空。
- memory validate：`AOS-000571` / `GREEN`，Delivery Receipt 865、Event 2226、Task Receipt 846。
- 独立只读终审：类型吞并阻断关闭，无剩余 blocker；runtime adapter SHA-256 `f2ad3abf7a9cdce98241d088728919b5a9757aeb990edf080fcc3cc088ff1bcf`。

## 文件摘要

- `ecommerce_business_investigation_review_command.py`：`914022653bf447a5ca06bef2e10ceac6f5a5734521a46f5e866e6e6fc0ef5789`
- `ecommerce_growth_runtime_adapters.py`：`f2ad3abf7a9cdce98241d088728919b5a9757aeb990edf080fcc3cc088ff1bcf`
- `test_ecommerce_review_advance_host.py`：`a78047d21fb3b96e1b86d0322c820ec67235b9e4340a96de67add2ad0fe280ad`
- `test_ecommerce_review_issue_eval_authority_pg.py`：`3016e102e7e5f00218db0134ac9168f868017dce6088d470bdbc2bfb2d32bbf4`
- 方案：`79e429e16bc04520c255e7c375bd54acba9eb751585c8e1b652bb523eebc85a1`

## 边界与下一步

本切片只关闭当前 OPEN ReviewIssue、真实 EvalReport 与其 subject Artifact 的 exact lineage。Review 命令所列四类 Artifact 的 actual Owner/family、AnalysisReceipt、Plan/Run 仍未全部回读，Review 不加入 readiness seal；无 Provider、TaskRun、Approval、发布或外部业务写入。下一切片继续四 Artifact actual authority，230 L0 挂起。
