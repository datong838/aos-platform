# W8-09 工程验收证据

- 任务：`workshop-w8-09-slo-alert-unknown-reconcile-usage-runbook-20260826`
- 代码提交：`f9f5fd64b9c024bdb8b23b9cf36b3cfbfe985444`
- 结论：`ENGINEERING_OPERATING_CONTRACT_BROWSER_GREEN / REAL_BASELINE_AND_DRILLS_BLOCKED / NO_EXTERNAL_EFFECT / NO_RELEASE`

## 自动化验证

- 专项：`3 files / 21 tests` GREEN。
- TypeScript：`tsc --noEmit` GREEN。
- Web 累计：`245 files / 2218 tests` GREEN；现有 React act、Router future flag 警告未升级为失败。
- 生产构建：`347 modules transformed` GREEN；保留既有大 chunk 提示。

## 内置浏览器验收

### 正式依赖失败关闭

在 `http://127.0.0.1:4189/workshop/task-cockpit` 使用正式构建、无本地 API 的条件下验收：Catalog 在 Module 挂载前失败关闭，页面保持唯一 H1、唯一 main、无横向溢出、无 uncaught error。此证据仅证明正式依赖缺失不会被伪装为已安装或 ready。

- 截图：`task-cockpit-catalog-fail-closed.png`
- SHA-256：`2680e4466d02999597e510b139147411696a13a7ebc7d02e17f4dbcb97d90ad3`

### 视觉夹具

为验收新卡片本身，临时使用只响应 GET 的本地视觉夹具：只挂载 `ecommerce.task-cockpit`，其 readiness 明确为 unknown；Task、SourceReadiness、运营 EvidencePack 等所有正式数据接口继续返回 503。浏览器确认：

- 唯一 H1 为“日常任务总控大屏”，唯一 main；1280×720 无横向溢出。
- W8-09 卡片显示 `运营失败关闭`、41 个独立缺口、Unknown backlog/oldest age/Usage 均为“未知（不以 0 代替）”、五轴 `0 / 5`、Runbook 未提供。
- 卡片内按钮数为 0；告警、Ack、Silence、Escalate、Resolve、Reconcile 全部禁用；无 Provider 调用、外部副作用或发布。
- 浏览器 error 级日志为 0；503 是夹具故意保留的 canonical 数据不可用边界。
- 截图：`operating-readiness-visual-fixture.png`
- SHA-256：`c50e86a77c47c2a5946096e8cdf5c5b2a93be12fb14f6a97d6f5ff00c86bb183`

视觉夹具不是 authority、真实 baseline、真实告警投影或 drill EvidencePack，不能用于签发 operational/release GREEN。
