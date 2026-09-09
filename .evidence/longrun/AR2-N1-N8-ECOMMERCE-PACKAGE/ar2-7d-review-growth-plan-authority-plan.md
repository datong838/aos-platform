# AR2-7D Review GrowthPlan 当前批准权威

基线 `m1@f21d5ad3`。依据 231-6 AR2-5 exact 输入与 AR2-7D-D1 ReviewAdvance 权威矩阵：GrowthPlan 必须由宿主在同一提交事务中证明为同租户、当前且 APPROVED；调用方携带的类型、revision 或状态声明均不构成权威。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：Review revalidate 将 `GrowthPlanRevision` 严格转换为现有 `AnalystExactRef`，在 HostTransaction 内锁定 `public.ecommerce_analyst_growth_plan_head`，并只从 public exact revision 与其 `public.ecommerce_analyst_authority_receipt` 回读原始正文；按 Owner 原算法重算 `{expectedVersion, revision}` 请求摘要并核对 receipt/result ref，要求命令 ref 与 Owner ref 完全一致、head 指向该 revision、lifecycle 为 approved。不可变 revision 不取行锁，以遵守其只读权限。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_review_growth_plan_authority_pg.py`：真实 18434 隔离 PG 验证当前 approved 接受，draft、旧 revision、hash 漂移与跨租户不可见拒绝，最终外层 rollback 无残留。
- 维护 Review Host 单测替身，只显式隔离本切片已由 PG 专项覆盖的 GrowthPlan Owner；其余 Receipt 纯编排断言不改。

## 边界与退出

不创建新表、不调用 Provider、不创建 TaskRun、不发布；只读锁不改变 GrowthPlan。ReviewIssue、EvalReport、Artifact、AnalysisReceipt、Plan/Run 的 exact Owner 回读仍须后续切片闭合，因此 Review 不加入 readiness seal。专项、邻接、closure、memory validate、diff check 和独立只读复核通过后提交。
