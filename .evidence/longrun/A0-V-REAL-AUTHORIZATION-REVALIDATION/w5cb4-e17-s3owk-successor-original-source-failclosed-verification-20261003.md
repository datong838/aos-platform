# E17 s3o-w-k 原 successor 来源失败封闭与 Content 来源盘点

基线 `aos-platform/m1@18ea80ca`、Authority `AOS-001219`；先复习 231/栖月汇/D-wave，读原 `aip_responsibility_assignment_store.py` 和 `aip_content_draft_store.py`，落 s3owk 文件级计划。当前真实库 `aos_current_preview_20260927@a0v_135` 只读，未改生产代码、迁移或 UI。

| 检查 | 证据 |
|---|---|
| successor 原方法 | 隔离 Growth1.13 签名 full-schema 库中，原 generic Plan 由独立非 owner Plan LOGIN create/revise 至 draft revision2；同身份调原 `AipResponsibilityAssignmentStore.create_successor`，精确 `sourcePlanRef` hash/revision/version 均指该 Plan。原 Store 按 `aip_responsibility_successor` replay → Plan `FOR UPDATE` → source revision 顺序执行，并以 `SOURCE_PLAN_NOT_EXACT_FROZEN` 拒绝；successor 行0。没有把缺 active SkillBinding 的 Plan 手改 frozen，也没有造 ResolutionReceipt/Run。 |
| Content 原来源 | 原 `AipContentDraftStore.register` 先要 ReadinessService READY 和 governed content-object verifier，然后同事务写 `aip_artifact`+共享 `content_draft.register` Receipt。现有 `tests/aip/test_aip9_content_draft_store.py` 正向是 `FakeConnection`/自造 ReadyService/ObjectVerifier；其14项与 successor scripted 测试合计 `14 passed`、exit0，只是旧单测基线，不能证明当前真实来源或受限 Content issuer。 |
| 专项 | 设置 `AOS_DATABASE_URL=<18435当前集群仅作一次性库创建连接>`、`AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=<本地签名回执>`，运行 `.venv/bin/python -m pytest -q --tb=short tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` → `1 passed`、exit0；该整测的原 BI/OCI 后续仍通过。`py_compile`、目标 `git diff --check` exit0。 |
| 零残留 | 真库只读：migration135、org-org/dev-project Plan0/successor0/共享 Receipt0；临时 issuer 角色0、`aos_test_*_ti4_test` 库0、隔离 OCI owner 容器0。Host/worker/Provider关闭。 |

复审：successor 原 Store 与原 Plan Store 共享 Plan head/revision 写域，但 successor 另有自己的配对记录，不能凭 Plan issuer SQL 权限就宣称正向；需要正式 frozen Plan、原 AssigneeResolutionReceipt 和无 TaskRun 的精确来源。Content 正向需要原 Readiness/Object authority 与独立 Content issuer 的配对守卫。下一波 s3o-w-l 先核可合法构造的正式来源，缺口逐项失败关闭，不能用手插 frozen Plan 或 fake ReadyService 冒充业务完成；BI `SET ROLE` 单项设计并行待办，长期 Goal 不因此停。
