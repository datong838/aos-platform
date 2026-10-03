# E17 s3o-w-i：原 Plan Store 受限发行切片计划

基线：`m1@dff21876`、权威 `AOS-001217`；当前真实库 `aos_current_preview_20260927@a0v_135` 只读，Host/worker/Provider 关闭。依据 231-3/4/5/9、栖月汇方案、D-wave s3o-w-i、前波 s3o-w-g/h。电脑重启后的 DB/API/Web 健康已在前波复核，本波不重启真库。

## 文件级范围与顺序

1. 先只读核验本地 Growth 1.13 签名回执及原 `test_growth_signed_installation_full_schema_pg.py` 的作用域。用原测试的独立 `aos_test_*_ti4_test` + 隔离 OCI 路径复核签名安装和 Plan preparation；结果仅为 test-only full-schema 证据，不进入当前实例。
2. 在 `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py` 写受限登录的单一辅助试验，并从 `test_growth_signed_installation_full_schema_pg.py` 已有原签名安装切片调用：原 `AipProductionContractStore.create_responsibility_plan`、原表、Plan issuer 最小 SELECT/INSERT/UPDATE、RLS/operation 约束；模板 authority 用同一隔离签名安装的真实 `ApprovedBIPreparationResolver`，不能以无来源 lambda 充作业务验收。原签名测试已在本日独立 `aos_test_*_ti4_test` 和隔离 OCI 上通过，exit 0。
3. RED 先覆盖缺 resolver 的 `RESPONSIBILITY_TEMPLATE_AUTHORITY_UNAVAILABLE` 与无合法签名安装时的拒绝；再验配对 head/revision/Receipt、同键回放/错 hash、跨租户、回滚、runtime 只读锁。若现有 ACL/原 Store 有缺口，只改最小测试协议或必要生产点，先复核产品/技术约束。
4. 专项和相邻回归、差异复审、verification；按精确路径提交 m1，再同步 01/06、D-wave、续接与 Prime。后续 successor/内容和正式迁移仍分波，不据隔离证明启当前 Host。

安全边界：不写当前真实库，不读商城源，不启当前 Host/Provider，不回放旧 Run，不手工 `run_definition`，不碰 230 L0；`dev-org` 仅零副作用隔离反例。签名回执存在不等于正式 Growth 1.13 当前发布或正式发行身份齐备。
