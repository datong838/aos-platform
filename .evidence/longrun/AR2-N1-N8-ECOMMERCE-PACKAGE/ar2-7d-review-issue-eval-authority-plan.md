# AR2-7D ReviewIssue / EvalReport 权威

基线 `m1@371dd7a0`。依据 231-6 AR2-5 exact 输入：ReviewIssue 必须为当前 OPEN version，EvalReport 必须真实存在，Issue→Eval→subject Artifact lineage 完全一致。现有平台 Owner 使用可变 `ReviewIssue(version)`，包合同使用 `ReviewIssueRevision` exact ref；需在宿主适配边界冻结唯一内容摘要，不能接受调用方自报状态。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_business_investigation_review_command.py`：新增纯函数，把 canonical `ReviewIssue` 完整 JSON（含 tenant/status/version/timestamps/refs）转换为 `ReviewIssueRevision` exact ref，摘要使用现有 production canonical hash；不写库、不改变旧 review command。
- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：Review revalidate 在同一 HostTransaction 对 `public.aip_review_issue` 当前行取共享锁，从该 public 行构造 canonical ReviewIssue 并核其 OPEN/version/exact ref；再从 `public.aip_eval_report_revision` 回读 issue 绑定的 exact EvalReport，重算报告摘要，要求命令 Eval ref、Issue eval ref、报告 subject Artifact 三方一致。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_review_issue_eval_authority_pg.py`，并维护 Review Host 纯编排替身：真实 PG 验证 OPEN 正例、关闭/版本/hash/Eval/subject/tenant/TEMP 漂移拒绝及 rollback。

## 边界与退出

不创建/解决/退回 Issue，不新增 Eval，不修改 Artifact；仅加锁读取。四 Artifact 的 actual Owner/family、AnalysisReceipt、Plan/Run 仍留后续，Review 不加入 readiness seal。专项、邻接、closure、memory validate、diff check和独立只读复核通过后提交；无 Provider、TaskRun、Approval、发布或外部业务写入。
