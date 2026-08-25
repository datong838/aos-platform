# W8-10 工程验收证据

- 任务：`workshop-w8-10-backup-projection-rebuild-rls-disaster-recovery-20260826`
- 代码提交：`d7eed3fee0915733d40cd1872493bdf486fdb844`
- 结论：`ENGINEERING_DR_CONTRACT_BROWSER_GREEN / REAL_RESTORE_AND_DRILLS_BLOCKED / NO_DATA_OPERATION / NO_EXTERNAL_EFFECT / NO_RELEASE`

## 自动化验证

- 专项：`3 files / 23 tests` GREEN。
- TypeScript：`tsc --noEmit` GREEN。
- Web 累计：`247 files / 2228 tests` GREEN；既有 React act、Router future flag 警告未升级为失败。
- 生产构建：`349 modules transformed` GREEN；保留既有大 chunk 提示。

## 内置浏览器验收

### 正式依赖失败关闭

在 `http://127.0.0.1:43110/workshop/task-cockpit` 使用正式构建且不提供本地 API：Catalog 在 Module 挂载前失败关闭，页面保持唯一 H1、唯一 main、1280×720 无横向溢出并显示“读取失败”。该路径只证明依赖缺失不会被伪装成已安装、灾备 ready 或恢复成功。

- 截图：`task-cockpit-catalog-fail-closed.jpg`
- SHA-256：`a42ea3f7651912f5d84399f0bc85826d8ab617900a15dbbd84f9e01941aa1c04`

### GET-only 视觉夹具

为验收 W8-10 卡片，临时使用只响应 GET 的本地视觉夹具：仅挂载 readiness=`unknown` 的 `ecommerce.task-cockpit`；Task、SourceReadiness 和所有 canonical 数据接口继续返回 503。浏览器确认：

- 唯一 H1 为“日常任务总控大屏”，唯一 main；视口 1280×720，无横向溢出。
- W8-10 卡片显示“灾备失败关闭”、34 个独立 blocker、authority inventory `0/8`、RLS `0/4`、external reconcile `0/5`、drills `0/10`。
- Backup manifest、Projection rebuild、RPO/RTO 均为“未知（不以 0 代替）”。
- 卡片内按钮为 0；页面不存在可执行 Restore/Rebuild/RLS/Failover/Failback 按钮。
- 截图：`dr-readiness-visual-fixture.jpg`
- SHA-256：`7f7b9f14c9027bc91b5dd214df9cce090291b967ee00d2e56cbc8c32bba5c88d`

视觉夹具已停止；它不是 authority、真实备份、RLS、RPO/RTO、RecoveryDecision Receipt 或 drill EvidencePack，不能用于签发 operational/release GREEN。

## 安全边界

本波没有读取备份内容、数据库或对象存储，没有连接隔离 DR target，没有 apply migration、restore、projection rebuild、RLS 变更、external reconcile、failover/failback、Provider/Action、真实租户写入、外部副作用或发布。
