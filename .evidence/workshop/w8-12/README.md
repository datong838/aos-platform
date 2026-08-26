# W8-12 运营就绪与发布决定工程验收证据

- 任务：`workshop-w8-12-operational-readiness-release-decision-20260826`
- 方案提交：`9667c15`
- 代码提交：`5b8ca21d914b893634399350662c659846869b5e`
- 基线 authority：`AOS-000281`
- 结论：`ENGINEERING_OPERATIONAL_DECISION_CONTRACT_BROWSER_GREEN / RELEASE_DECISION_NO_GO / BACKEND_AND_SECURITY_BASELINE_RED / NO_REAL_TENANT_MUTATION / NO_EXTERNAL_EFFECT / NO_RELEASE`

## 工程验证

- W8-12 专项：`3 files / 27 tests` GREEN。
- Web 累计：`251 files / 2252 tests` GREEN。
- Web TypeScript GREEN；Desktop TypeScript GREEN。
- Web 生产构建：`353 modules transformed` GREEN，保留既有大 chunk 提示。
- Security 扫描器自测：`9 tests` GREEN；仓库扫描仍为 `files=5026 / critical=5 / warning=326` RED。5 个 critical 仍位于两个既有 runtime 私钥文件和三个测试凭据 URL 样例；本波未读取、复制、输出、删除或豁免密钥内容。
- Backend 沿用 W8-11 同一连续工程周期的最新全量基线：收集 `12461` 项，pytest lastfailed cache 为 `335` 项，状态 RED。本波没有通过重跑子集、清缓存或修改数据把它伪装为 GREEN。
- `git diff --check` GREEN。

八项能力 readiness、精确候选、W8-11 累计门、maker/checker 审批、滚动/停止/回滚/值班/审计及发布后 Receipt 均按缺失即失败关闭。页面显示 `0/8` ready、`8 blocked` 和 `14 blockers`；批准、Feature Flag、启动/停止 rollout、回滚、fail-forward 和 release 命令全部为 `false`。

## 内置浏览器验收

### 正式依赖失败关闭

在 `http://127.0.0.1:43113/workshop/task-cockpit` 使用正式生产构建且不提供本地 API。Catalog 在模块挂载前失败关闭；页面保持唯一 H1、唯一 main、1280×720 无横向溢出，W8-12 卡片不会被伪装成已安装。

- 截图：`task-cockpit-catalog-fail-closed.jpg`
- SHA-256：`2680e4466d02999597e510b139147411696a13a7ebc7d02e17f4dbcb97d90ad3`

### GET-only 视觉夹具

临时 GET-only 夹具仅挂载 `ecommerce.task-cockpit`；其他 canonical 数据接口继续返回 503。内置浏览器确认：

- 唯一 H1 为“日常任务总控大屏”，唯一 main，1280×720 无横向溢出。
- W8-12 显示 `NO_GO · 失败关闭`、八项能力全部 blocked、`0 / 8`、`8 blocked` 和 `14 blockers`。
- Candidate、W8-11、Approval、Rollout/Rollback、Decision Receipt 均显示缺失或阻断。
- 卡片按钮为 0；页面没有批准、Feature Flag、rollout、回滚或发布按钮。
- 截图：`operational-release-no-go-visual-fixture.jpg`
- SHA-256：`dc0e2c3f05dc845f1f9c1a63ed70b11cb85a39f5150a74f2f37b7834124f9219`

视觉夹具已停止；它不是 authority、真实租户 EvidencePack、候选批准、运营 Receipt 或发布授权。

## 安全边界

本波没有读取或修改真实业务数据，没有执行 migration apply、Bundle 安装、Feature Flag、Provider/Action、真实租户写入、外部副作用或发布。W8-12 只闭合 96 项工程清单中的最后一个只读决定合同；工程清单完成不等于产品冻结、运营就绪或获准发布。
