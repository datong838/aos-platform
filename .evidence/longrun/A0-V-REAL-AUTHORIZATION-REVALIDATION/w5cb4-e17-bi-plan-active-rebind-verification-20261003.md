# W5CB4 E17｜签名 BI Plan active 重绑定验证

## 范围与实现

- 上位依据：231-3 当前 frozen `ResponsibilityPlanRevision`/精确 `roleRefs`，BG00ds approved 准备命令，550 的原签名安装 active 旧引用漂移。文件级方案见同目录 `w5cb4-e17-bi-plan-active-rebind-plan-20261002.md`。
- 原 Plan 修订 Store 增加调用方持有事务的原语；普通修订路由仍使用原 operation 与请求哈希。专用 rebind 在同事务核当前 active 安装/强 ETag、正式 OIDC actor 与当前持久权限、原 prepare Receipt、原 draft Plan hash、Plan head CAS、签名 Registry/模板与六实例依赖，只替换模板 exact revision 并产生新 draft/一次 Receipt；提交前再核签名源。未知写结果只准按原幂等键、actor 和租户只读回读 Receipt，不据此重发。
- 本波不冻结 Plan、不配置 Host、不创建当前正式身份、不写真实当前库。

## RED/GREEN 与回归

- RED：隔离 PG 事务测试首次因缺 `revise_responsibility_plan_in_transaction` 报 `AttributeError`，exit 1；实现后目标测试 `1 passed`，exit 0。
- Growth1.13 原签名 Registry→安装→OCI→runtime apply/verify→active→重绑定及负向链：最终 `1 passed, 7 warnings`，exit 0。回读模型 `installationETag` 大写别名曾 RED，已精确修正并重跑 GREEN。Growth1.12 原链 `1 passed, 7 warnings`，exit 0。
- 相邻 BI/Plan Store/API 九文件：`111 passed, 8 warnings in 47.06s`，exit 0；`py_compile` 与本波精确 `git diff --check`，exit 0。
- Growth 隔离链仅在 `aos_test_*_ti4_test` 库，六实例为显式测试前置数据；不能充作当前实例的正式生产者或外部 OIDC 证明。异常回滚、同键重放/异请求冲突、错误 ETag/Plan head/prepare key/trust/actor/tenant 均失败关闭。

## 页面与当前实例

- 2026-10-03 00:15 CST，浏览器 `http://127.0.0.1:8434/aip/skill-publish`：`org-org/dev-project`、37 仅评测、0 已发布、三项发布阻断、按钮 disabled、侧栏无电商入口；浏览器截图在本轮工具证据。API 8080 与 Web 8434 LISTEN，Runtime Host 18181 无监听。`curl` Web 页面 HTTP 200；`/health` 路由 HTTP 404，因此不把该路径当健康证明。
- 当前权威卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135` 继续只读；本波测试只在隔离库。页面是已部署旧代码的禁入验收，不声称新路由已在当前 API 热加载或首链完成。

## 复审与剩余风险

- 与方案一致：严格保留 approved→active 的版本差异，只在当前签名源重验和原 Receipt 一致时新增 draft；只读 Receipt 的 `current_admission_verified=false`。旧普通 Plan 修订语义/测试不变。
- 原正式 OIDC、独立 API/目录/Web/Host 身份、Growth1.13 正式签发与当前八配置/Owner/assignment 仍缺；Host 继续禁入。下一波应先做同源受控冻结与配置 Reader 联合 RED，外部身份缺口只阻断当前实例，不阻断隔离研发。
