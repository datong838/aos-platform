# E17 s3o-w-k：successor 与 Content 原写者隔离切片计划

基线 `aos-platform/m1@18ea80ca`、Authority `AOS-001219`。复习 231-3/4/5/9、栖月汇方案与 D-wave；当前权威库 `aos_current_preview_20260927@a0v_135` 只读，正式 Growth1.13/issuer/Host 仍缺。前波 BI 独立 issuer 的 `SET LOCAL ROLE aos_runtime` 拒绝只限该路径，不阻本波。

## 文件级范围

1. `services/aos-api/aos_api/aip_responsibility_assignment_store.py` 原 `create_successor` 直接读取 frozen Plan、无 TaskRun、目标 AssigneeResolution，然后同事务 INSERT 新 Plan head/revision 和 `aip_responsibility_successor`，并不写共享 ProductionContractReceipt。旧 `tests/test_w3_07_responsibility_assignment.py` 仅 scripted connection；先在隔离 full-schema 签名测试中用原 Store 与独立 Plan issuer 对现有 draft Plan 复现 `SOURCE_PLAN_NOT_EXACT_FROZEN` 且 successor 零增量。不得人工把未就绪 Plan 改成 frozen 来冒充当前业务通过。
2. `services/aos-api/aos_api/aip_content_draft_store.py` 原 `register` 先由 ReadinessService 和 governed object verifier 授权，再同事务 INSERT `aip_artifact` 与 `content_draft.register` 共享 Receipt；旧 `tests/aip/test_aip9_content_draft_store.py` 正向使用 FakeConnection/ReadyService/VerifiedContentObject，不能用作真数据验收。先核当前正式 Readiness/Object authority 是否可构造；缺来源时原方法必须在连接数据库前失败封闭。后续真实原写路正向需要独立 Content issuer + 原来源，另切片实现。
3. 新增代码仅限 `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py` 与签名测试接线，先 RED 记录第一权限/依赖拒绝；若有合法原前置来源，再做最小受限 ACL/同事务正向、幂等/CAS/回滚/读者锁。否则只收失败封闭并登记精确未完成项，不用 test mock 宣称业务通过。

专项/相邻、资源清理、真库只读回读、方案一致性复审和 verification 后才可精确提交。正式 ACL/OIDC、当前库迁移、Host/worker/Provider、旧 Run/商城源/230 L0 均不在本波。
