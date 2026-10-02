# E17 Growth 1.13 原签名 BI 模板选择器验证

基线 `aos-platform/m1@dc59eea3`、`AOS-001160`。方案见同前缀 `plan`。改动仅限原 `ApprovedBIPreparationResolver._installation_rows` 的 Growth 版本允许集合及原全 schema 签名安装测试。当前权威 PostgreSQL 库只读，未启动 Host/worker/Provider。

## RED→GREEN

- 隔离 PG/OCI 原 Registry 发布→签名检查→获批安装 Growth `1.13.0`，再由原 BI 模板选择器读取：改动前 `1 failed, 7 warnings`，断言 `selected_template is not None` 失败，退出 1。测试保留隔离库；该本地签名不是当前正式发布来源。
- 最小实现将 SQL `version.version='1.12.0'` 改为 `version.version IN ('1.12.0','1.13.0')`。同测试 `1 passed, 7 warnings`，退出 0；进一步补空信任根、`dev-org` 负例后再次 `1 passed, 7 warnings`，退出 0。原 exact lock、Registry release、签名、artifact 字节、唯一选择逻辑未改。
- 原 `1.12.0` 全 schema 签名安装同测试 `1 passed, 7 warnings`，退出 0。
- 相邻模板权威、BI 原入口与 Growth 1.13 候选包测试 `65 passed, 7 warnings`，退出 0。
- 两文件 `py_compile`、精确路径 `git diff --check` 退出 0。

## 当前实例与复审

- `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -Atc 'SELECT version_num FROM alembic_version;'` → `a0v_135`。API `/v1/health` → `{"status":"ok"}`；OCI owner 容器列表为空。
- in-app browser `http://127.0.0.1:8434/aip/skill-publish` 回读 `org-org/dev-project`：37 仅已评测、0 已发布，三项发布阻断、发布按钮禁用，工作台无可见入口；截图在本波浏览器工具输出。页面无本波改动。
- 方案与代码一致：仅使已正式签名、同租户获批安装的 Growth 1.13 BI 模板能被原准备选择器识别。它没有创建当前 Plan、八配置或正式 OIDC/身份/信任根；1.13 本地 test-only 签名不升格当前授权。旧 1.12 正链保留，其他版本不在 SQL 允许集合。

## 后续

E17 当前实例仍需正式 Growth 1.13 signer/checker/trust/OCI、独立身份、OIDC、正式 actor/审批、六类配置与预算来源、精确 Host assignment/Owner，之后才可做配置和自然首链。下波优先复核原 BI Plan 正式 actor/Receipt 到冻结计划与配置组装的来源联结；若当前外部身份仍缺，在隔离 PG 继续原生产者正反链，不写当前库。
