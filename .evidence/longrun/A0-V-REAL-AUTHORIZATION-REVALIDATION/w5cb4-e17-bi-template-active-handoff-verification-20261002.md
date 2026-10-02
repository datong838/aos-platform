# W5CB4 E17｜签名 BI 模板 approved→active 接续验证

基线 `aos-platform/m1@e2c61736`、`AOS-001161`。方案见同前缀 `plan`。本波只改原 Growth 签名完整 schema 隔离链测试；生产代码和当前实例没有变更。

## 原生产者证据

- Growth 1.13 的原 Registry 发布、签名检查、approved 安装下，`ApprovedBIPreparationResolver` 选出安装与 exact BI 模板；`ActiveBIBusinessResolver` 拒绝。原 runtime-apply/verify 进入 active 后，后者只对同租户同安装、当前安装修订的模板返回正例；旧 approved 选择器拒绝。空 trust 与 `dev-org` 均拒绝。完整 PG/OCI 测试 `1 passed, 7 warnings`，exit 0。
- Growth 1.12 同链 `1 passed, 7 warnings`，exit 0；BI 模板/权限/就绪相邻回归 `79 passed, 7 warnings`，exit 0；`py_compile`、精确 `git diff --check` 均 exit 0。没有为刷新进度制造生产实现。
- 新的反证：approved 选择的模板引用安装修订 3；verify 后 active 选择器返回更高的当前修订，模板内容哈希不变。`active_resolver.resolve(scope, old_approved_ref)` 为 False，当前 active ref 为 True。这是安全所需的旧引用失败关闭，也意味着 BG00ds 预备的 Plan draft 不能直接以旧 exact ref 冻结成当前配置。下一波必须追原 `bi_responsibility_plan.prepare` Receipt，并设计正式 actor、强 ETag、当前签名安装和 Plan CAS 下的受控重绑定/冻结顺序；不能改成允许旧安装修订通过。

## 当前实例与页面

- `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -Atc 'SELECT version_num FROM alembic_version;'` → `a0v_135`；API `/v1/health` 200 `{"status":"ok"}`；Web `/aip/skill-publish` 200；`lsof -nP -iTCP:18181 -sTCP:LISTEN` exit 1，无 Host 监听；OCI owner 容器列表为空。
- in-app browser 同页回读 `org-org/dev-project`、37 仅已评测、0 发布、三项阻断、发布按钮 disabled、无可见电商入口；截图在本波浏览器工具输出。隔离测试的本地签名不属于当前正式信任根；当前 OIDC/三身份、八配置、Owner、assignment、Growth1.13 正式发布与首链仍缺。

## 方案复审与剩余风险

`231-3` 的 approved→apply→verify→active 顺序及 BG00ds 的“只产草稿”边界保持。新增断言没有给通用 Plan 冻结、配置或 Host 放权。真正待解的是旧草稿在状态迁移后的 exact ref 漂移，下一波需用原 Plan/Receipt 生产者做正反链和最小实现；本波仅证明并定位，不宣称当前业务闭环。
