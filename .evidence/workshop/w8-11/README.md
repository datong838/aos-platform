# W8-11 累计发布门工程验收证据

- 任务：`workshop-w8-11-cumulative-release-gate-20260826`
- 代码提交：`b20d98014770bb806b2064130dfe229570241683`
- Desktop 兼容提交：`7e11fb7a472954cd2fd597ce310f0b35b85f5778`
- 基线 authority：`AOS-000280`
- 结论：`ENGINEERING_CUMULATIVE_GATE_BROWSER_GREEN / RELEASE_LEDGER_POSITIVE_EVIDENCE_BLOCKED / BACKEND_AND_SECURITY_BASELINE_RED / NO_MIGRATION_APPLY / NO_EXTERNAL_EFFECT / NO_RELEASE`

## 工程验证

- W8-11 专项：`3 files / 26 tests` GREEN。
- W8-11 与 Desktop 兼容相关：`5 files / 60 tests` GREEN。
- Web 累计：`249 files / 2240 tests` GREEN；生产构建 `351 modules transformed` GREEN，保留既有大 chunk 提示。
- Web TypeScript GREEN；Desktop TypeScript 在替换不受当前 target 支持的 `Array.at` / `String.replaceAll` 后独立回跑 GREEN。
- OpenAPI：生成物确定性/current 校验与 `16 tests` GREEN，保留既有 `7 warnings`。
- SDK：`1 file / 7 tests` GREEN。
- Desktop：`9 files / 40 tests` GREEN。
- Helm：lint、default/prod render 与确定性校验 GREEN；default SHA-256 `c1e4b5b9b8ac0a29cc460dd5c8f35c097c08caa54d8af07095b8af12dd824ee6`，prod SHA-256 `e98d6277698db94030face2205de02a8aafc4dcd4473bad4b982138761f288f3`。
- Alembic：只读脚本图核验为单头 `w7_006`、单 base `6cd2ca0eff8f`；没有执行 upgrade/downgrade 或任何 migration apply。
- `git diff --check` GREEN；未修改 OpenAPI、Alembic、Bundle lock 或生成物。完整后端测试产生了 3 个未跟踪 D5 test evidence，保持原样且未纳入本波提交。

统一 `scripts/ci.sh wave` 的当前结果是 `7 passed / 3 failed / 10 total`，不能包装为累计 GREEN：

1. Backend 全量收集 `12461` 项，pytest lastfailed cache 记录 `335` 项。主要包含历史 PostgreSQL `ON CONFLICT` 约束不匹配、JDBC/MySQL fixture context-manager 错误，以及 downgrade 在检测到 authority 数据时按设计拒绝继续。没有删除或修改数据来规避失败。
2. Desktop TypeScript 在统一命令时失败；本波随后完成最小兼容修复并独立回跑 GREEN。
3. Security 扫描器自测 `9 tests` GREEN，但仓库扫描仍为 `files=5018 / critical=5 / warning=326`。5 个 critical 位于两个既有 runtime 私钥文件与三个测试凭据 URL 样例；未读取、复制或输出密钥内容，也未自动删除或豁免。

因此，十四栏 ledger 没有同一 immutable release identity 下的完整正向 EvidencePack，`org-org/dev-project` 正向与 `dev-org/dev-project` 负向也没有同 cutoff 的 release 证据。页面保持 `0/14`、八 Module `0/8`，unknown 不按 0 或 GREEN 解释。

## 内置浏览器验收

### 正式依赖失败关闭

在 `http://127.0.0.1:43111/workshop/task-cockpit` 使用正式生产构建且不提供本地 API。Catalog 在模块挂载前失败关闭；页面保持唯一 H1、唯一 main、1280×720 无横向溢出并显示“读取失败”，W8-11 卡片不会被伪装成已安装。

- 截图：`task-cockpit-catalog-fail-closed.jpg`
- SHA-256：`2680e4466d02999597e510b139147411696a13a7ebc7d02e17f4dbcb97d90ad3`

### GET-only 视觉夹具

临时 GET-only 夹具仅挂载 readiness=`unknown` 的 `ecommerce.task-cockpit`；Task、SourceReadiness 和其他 canonical 数据接口继续返回 503。内置浏览器确认：

- 唯一 H1 为“日常任务总控大屏”，唯一 main，1280×720 无横向溢出。
- W8-11 显示“累计门失败关闭”、十四栏全部 `unknown`、Logic `0/14`、数字同事绑定 `0/8`、26 个独立 blocker。
- release identity、tenant negatives、Receipt readback 均显示“未知（不以 0/历史值代替）”。
- 卡片按钮为 0；页面没有 Migration、Install 或 Release 按钮。
- 截图：`cumulative-release-gate-visual-fixture.jpg`
- SHA-256：`6f8c947782ecf9ce31098a6420ecd0ea23e5a46b204400d25892f20ac4847302`

视觉夹具已停止；它不是 authority、真实租户 EvidencePack、Bundle Installation、运营 Receipt 或发布批准。

## 安全边界

本波没有读取或修改真实业务数据，没有执行 migration apply、Bundle 安装、生成物改写、安全自动修复、Provider/Action、真实租户写入、外部副作用或发布。累计基线 RED 会继续传递到 W8-12 的 `NO_GO`，不会阻止后续只读工程合同继续施工。
