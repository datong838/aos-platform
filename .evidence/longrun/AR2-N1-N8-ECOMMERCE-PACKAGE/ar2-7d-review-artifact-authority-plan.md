# AR2-7D Review 四 Artifact 权威

基线 `m1@2e9827d9`。依据 231-6 AR2-5 exact 输入，Review 的四个固定 family Artifact 必须来自唯一 AIP/L0 append-only `aip_artifact` authority，不能只信调用方提供的四个不同 ref；ReviewIssue/Eval subject 还必须落在该四项集合内。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：同一 HostTransaction 直读 `public.aip_artifact` 四行，要求 artifact_type 与 `portrait/diagnosis/growth_plan/evidence_summary` 一一对应，命令 revision 等于真实 `family_revision`（standalone artifact 固定为 1），id/hash 精确一致，四项来自同一非空 AIP TaskRun；ReviewIssue/Eval subject 必须命中其中一项。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_review_artifact_authority_pg.py`，并维护 Review Host 纯编排替身。真实 PG 验证四 family 正例、type/hash/revision/缺失/run/subject/tenant/TEMP 漂移拒绝及 rollback。

## 边界与退出

本切片只读取 append-only Artifact；不读取或存储正文，不创建/更新 Artifact，不推断 artifact family selection 已批准，也不把 AIP TaskRun 等同于 BusinessInvestigationRun。AnalysisReceipt、Plan/Run 及其 compilation TaskRun 连接留后续；Review 不加入 readiness seal。专项、邻接、closure、memory validate、diff check和独立只读复核通过后提交；无 Provider、TaskRun、Approval、发布或外部业务写入。
